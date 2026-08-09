"""Casos de uso de áreas y su composición.

Todo cambio deja rastro en `audit_log` (RN-REP-007, ADR-031). No es celo: la
composición de un área **es** quién se entera de qué, así que sacar a alguien
de Gerencia es exactamente el tipo de acto de autoridad que un auditor viene
a revisar.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.reports.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.reports.infrastructure.models import Area, AreaMiembro
from src.modules.reports.infrastructure.repositories import AreaRepo
from src.modules.users.infrastructure.models import (
    Rol,
    Sucursal,
    Usuario,
    UsuarioSucursal,
)
from src.shared import auditoria


def _foto(area: Area) -> dict:
    return {"codigo": area.codigo, "nombre": area.nombre, "activa": area.activa}


def crear_area(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    codigo: str,
    nombre: str,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> Area:
    repo = AreaRepo(session)
    if repo.por_codigo(empresa_id, codigo) is not None:
        raise Conflicto(f"ya existe un área con código '{codigo}' en esta empresa")
    area = repo.add(Area(empresa_id=empresa_id, codigo=codigo, nombre=nombre))
    auditoria.registrar(
        session,
        entidad="area",
        accion="crear",
        entidad_id=area.id,
        usuario_id=actor_id,
        datos_despues=_foto(area),
        empresa_id=empresa_id,
        ip=ip,
    )
    return area


def editar_area(
    session: Session,
    area_id: uuid.UUID,
    *,
    nombre: str | None = None,
    activa: bool | None = None,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> Area:
    area = AreaRepo(session).get(area_id)
    if area is None:
        raise NoEncontrado("área no encontrada")
    antes = _foto(area)
    if nombre is not None:
        area.nombre = nombre
    if activa is not None:
        area.activa = activa
    auditoria.registrar(
        session,
        entidad="area",
        accion="editar",
        entidad_id=area.id,
        usuario_id=actor_id,
        datos_antes=antes,
        datos_despues=_foto(area),
        empresa_id=area.empresa_id,
        ip=ip,
    )
    return area


def borrar_area(
    session: Session,
    area_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    """Borra el área solo si ninguna regla la nombra.

    Con reglas colgando, borrarla las dejaría apuntando a la nada y el hecho
    pasaría a no llegarle a nadie sin que nadie lo haya decidido. Para dejar
    de usarla sin romper las reglas está `activa = false`.
    """
    from src.modules.reports.infrastructure.models import ReglaDestinatario

    area = AreaRepo(session).get(area_id)
    if area is None:
        raise NoEncontrado("área no encontrada")
    en_uso = session.scalar(
        select(ReglaDestinatario.id).where(ReglaDestinatario.area_id == area_id)
    )
    if en_uso is not None:
        raise Conflicto(
            "el área es destinataria de alguna regla; desactivarla en vez de borrarla"
        )
    antes = _foto(area)
    empresa_id = area.empresa_id
    for miembro in AreaRepo(session).miembros(area_id):
        session.delete(miembro)
    session.delete(area)
    auditoria.registrar(
        session,
        entidad="area",
        accion="borrar",
        entidad_id=area_id,
        usuario_id=actor_id,
        datos_antes=antes,
        empresa_id=empresa_id,
        ip=ip,
    )


def _exigir_de_la_empresa(
    session: Session, empresa_id: uuid.UUID, *, usuario_id: uuid.UUID | None,
    sucursal_id: uuid.UUID | None,
) -> None:
    """Un miembro tiene que ser de la empresa del área (RN-REP-006).

    `Rol` no se valida porque es global (no tiene `empresa_id`): lo que acota
    el alcance de un rol es la sucursal del usuario que lo tiene, y eso ya lo
    resuelve `destinatarios._usuarios_de_rol` al filtrar por sucursal.
    """
    if sucursal_id is not None:
        sucursal = session.get(Sucursal, sucursal_id)
        if sucursal is None or sucursal.empresa_id != empresa_id:
            raise ReglaNegocio("la sucursal no pertenece a la empresa del área")
    if usuario_id is not None:
        if session.get(Usuario, usuario_id) is None:
            raise NoEncontrado("usuario no encontrado")
        pertenece = session.scalar(
            select(UsuarioSucursal.usuario_id)
            .join(Sucursal, Sucursal.id == UsuarioSucursal.sucursal_id)
            .where(
                UsuarioSucursal.usuario_id == usuario_id,
                Sucursal.empresa_id == empresa_id,
            )
        )
        if pertenece is None:
            raise ReglaNegocio("el usuario no pertenece a la empresa del área")


def agregar_miembro(
    session: Session,
    area_id: uuid.UUID,
    *,
    rol_id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> AreaMiembro:
    repo = AreaRepo(session)
    area = repo.get(area_id)
    if area is None:
        raise NoEncontrado("área no encontrada")
    if (rol_id is None) == (usuario_id is None):
        raise ReglaNegocio("un miembro es un rol o un usuario, no los dos ni ninguno")
    if rol_id is not None and session.get(Rol, rol_id) is None:
        raise NoEncontrado("rol no encontrado")
    _exigir_de_la_empresa(
        session, area.empresa_id, usuario_id=usuario_id, sucursal_id=sucursal_id
    )

    miembro = repo.add_miembro(
        AreaMiembro(
            area_id=area_id,
            rol_id=rol_id,
            usuario_id=usuario_id,
            sucursal_id=sucursal_id,
        )
    )
    auditoria.registrar(
        session,
        entidad="area_miembro",
        accion="crear",
        entidad_id=miembro.id,
        usuario_id=actor_id,
        datos_despues={
            "area": area.codigo,
            "rol_id": str(rol_id) if rol_id else None,
            "usuario_id": str(usuario_id) if usuario_id else None,
            "sucursal_id": str(sucursal_id) if sucursal_id else None,
        },
        empresa_id=area.empresa_id,
        sucursal_id=sucursal_id,
        ip=ip,
    )
    return miembro


def quitar_miembro(
    session: Session,
    miembro_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    repo = AreaRepo(session)
    miembro = repo.miembro(miembro_id)
    if miembro is None:
        raise NoEncontrado("miembro no encontrado")
    area = repo.get(miembro.area_id)
    auditoria.registrar(
        session,
        entidad="area_miembro",
        accion="borrar",
        entidad_id=miembro_id,
        usuario_id=actor_id,
        datos_antes={
            "area": area.codigo if area else None,
            "rol_id": str(miembro.rol_id) if miembro.rol_id else None,
            "usuario_id": str(miembro.usuario_id) if miembro.usuario_id else None,
            "sucursal_id": str(miembro.sucursal_id) if miembro.sucursal_id else None,
        },
        empresa_id=area.empresa_id if area else None,
        sucursal_id=miembro.sucursal_id,
        ip=ip,
    )
    session.delete(miembro)
