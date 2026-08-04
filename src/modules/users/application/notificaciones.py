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
    Notificacion,
    Rol,
    UsuarioRol,
    UsuarioSucursal,
)

log = logging.getLogger("provecho.app")

# Roles que cubren el local cuando no hay caja abierta que diga quién está
# de turno. En orden de cercanía a la operación.
ROLES_RESPALDO = ("supervisor", "admin")


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
