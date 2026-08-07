"""Bandeja de notificaciones y a quién le llega cada aviso.

**El punto de configuración futuro está en `destinatarios_de_sucursal`.**
Hoy la regla es fija —encargado de turno, con supervisores como respaldo—
porque una tabla de preferencias sin nadie que la administre es un formulario
más y el mismo resultado. Cuando haga falta ("de noche avisar también al
dueño", "este local no usa la bandeja"), se cambia esa función y nada más:
ni el listener ni la entidad ni la pantalla saben cómo se eligió.
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.accounting.application.queries_publicas import encargado_de_turno
from src.modules.users.infrastructure.models import (
    Almacen,
    Notificacion,
    Rol,
    Sucursal,
    UsuarioRol,
    UsuarioSucursal,
)

log = logging.getLogger("provecho.app")

# Roles que cubren el local cuando no hay caja abierta que diga quién está
# de turno. En orden de cercanía a la operación.
ROLES_RESPALDO = ("supervisor", "admin")

# Quién responde por lo que pasa dentro de un almacén. `almacenero` primero
# porque es quien puede actuar; los otros dos porque tienen que enterarse.
ROLES_ALMACEN = ("almacenero", "supervisor", "admin")


def destinatarios_de_sucursal(
    session: Session, sucursal_id: uuid.UUID
) -> list[uuid.UUID]:
    """A quién se le avisa de algo que pasa en esta sucursal.

    1. El **encargado de turno**, derivado de la caja abierta: es quien
       está a cargo del local ahora mismo.
    2. Si no hay caja abierta (local cerrado, o abrieron sin registrarla),
       los `supervisor`/`admin` asignados a esa sucursal — un aviso sin
       destinatario es un aviso perdido, y prefiere avisarle a alguien de
       más que a nadie.

    Devuelve lista vacía si no hay nadie asignado. El llamador lo registra y
    sigue: no poder avisar no puede tumbar la operación que originó el aviso.
    """
    encargado = encargado_de_turno(session, sucursal_id)
    if encargado is not None:
        return [encargado]

    respaldo = list(
        session.scalars(
            select(UsuarioSucursal.usuario_id)
            .join(UsuarioRol, UsuarioRol.usuario_id == UsuarioSucursal.usuario_id)
            .join(Rol, Rol.id == UsuarioRol.rol_id)
            .where(
                UsuarioSucursal.sucursal_id == sucursal_id,
                Rol.nombre.in_(ROLES_RESPALDO),
            )
            .distinct()
        )
    )
    if not respaldo:
        log.warning(
            "Aviso sin destinatario: la sucursal no tiene caja abierta ni "
            "supervisores asignados",
            extra={"sucursal_id": str(sucursal_id)},
        )
    return respaldo


def destinatarios_de_almacen(
    session: Session,
    almacen_id: uuid.UUID,
    roles: tuple[str, ...] = ROLES_ALMACEN,
) -> list[uuid.UUID]:
    """A quién se le avisa de algo que pasa en un **almacén**.

    No alcanza con `destinatarios_de_sucursal`: el almacén central y el de
    producción no cuelgan de ninguna sucursal (`almacen.sucursal_id` NULL),
    y ahí no hay encargado de turno que valga. La regla es por rol:

    - Almacén **de sucursal**: los roles de almacén asignados a esa
      sucursal, más el encargado de turno — es quien está parado ahí ahora.
    - Almacén **de empresa** (central, producción): los roles de almacén
      asignados a cualquier sucursal de esa empresa. Es más gente de la
      necesaria, y es a propósito: un aviso de stock del central sin
      destinatario es un aviso perdido.

    Como `destinatarios_de_sucursal`, esta función es el punto de
    configuración futuro: cambiarla no toca listeners, entidad ni pantalla.
    """
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        return []

    q = (
        select(UsuarioSucursal.usuario_id)
        .join(Sucursal, Sucursal.id == UsuarioSucursal.sucursal_id)
        .join(UsuarioRol, UsuarioRol.usuario_id == UsuarioSucursal.usuario_id)
        .join(Rol, Rol.id == UsuarioRol.rol_id)
        .where(Rol.nombre.in_(roles))
        .distinct()
    )
    if almacen.sucursal_id is not None:
        q = q.where(UsuarioSucursal.sucursal_id == almacen.sucursal_id)
    else:
        q = q.where(Sucursal.empresa_id == almacen.empresa_id)

    destinatarios = list(session.scalars(q))
    if almacen.sucursal_id is not None:
        encargado = encargado_de_turno(session, almacen.sucursal_id)
        if encargado is not None and encargado not in destinatarios:
            destinatarios.append(encargado)
    if not destinatarios:
        log.warning(
            "Aviso sin destinatario: el almacén no tiene roles de almacén "
            "asignados en su empresa",
            extra={"almacen_id": str(almacen_id)},
        )
    return destinatarios


def notificar(
    session: Session,
    destinatarios: list[uuid.UUID],
    *,
    tipo: str,
    titulo: str,
    cuerpo: str | None = None,
    nivel: str = "aviso",
    referencia_tipo: str | None = None,
    referencia_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
) -> list[Notificacion]:
    """Crea una notificación por destinatario. Sin destinatarios, no hace
    nada (y no es un error: ya se registró arriba)."""
    creadas = []
    for usuario_id in destinatarios:
        fila = Notificacion(
            usuario_id=usuario_id,
            tipo=tipo,
            nivel=nivel,
            titulo=titulo,
            cuerpo=cuerpo,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            sucursal_id=sucursal_id,
        )
        session.add(fila)
        creadas.append(fila)
    return creadas


def q_bandeja(usuario_id: uuid.UUID, *, solo_no_leidas: bool = True):
    """La consulta de la bandeja, sin ejecutar: el router la pagina
    (ADR-026). La bandeja de alguien que estuvo de vacaciones no cabe en
    una pantalla."""
    stmt = select(Notificacion).where(Notificacion.usuario_id == usuario_id)
    if solo_no_leidas:
        stmt = stmt.where(Notificacion.leida_at.is_(None))
    return stmt.order_by(Notificacion.created_at.desc())


def bandeja(
    session: Session,
    usuario_id: uuid.UUID,
    *,
    solo_no_leidas: bool = True,
    limite: int = 50,
) -> list[Notificacion]:
    stmt = q_bandeja(usuario_id, solo_no_leidas=solo_no_leidas)
    return list(session.scalars(stmt.limit(limite)))


def marcar_leida(
    session: Session, notificacion_id: uuid.UUID, usuario_id: uuid.UUID
) -> Notificacion | None:
    """`None` si no existe o es de otro: la respuesta no confirma la
    existencia de la notificación ajena."""
    fila = session.get(Notificacion, notificacion_id)
    if fila is None or fila.usuario_id != usuario_id:
        return None
    if fila.leida_at is None:
        fila.leida_at = func.now()
    return fila


def marcar_todas_leidas(session: Session, usuario_id: uuid.UUID) -> int:
    filas = list(
        session.scalars(
            select(Notificacion).where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.leida_at.is_(None),
            )
        )
    )
    for fila in filas:
        fila.leida_at = func.now()
    return len(filas)
