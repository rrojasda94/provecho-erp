"""Bandeja de notificaciones: la campana de un usuario.

**Solo bandeja.** A quién le llega cada aviso ya no se decide acá: eso es el
módulo `reports` (ADR-033), que resuelve destinatarios contra reglas
administrables y publica `reports.reporte_emitido` con la lista ya resuelta.
Hasta 2026-08-08 este archivo tenía `destinatarios_de_sucursal` y
`destinatarios_de_almacen` con la regla fija cableada, y su propio docstring
declaraba que ese era «el punto de configuración futuro». Las dos funciones
se mudaron tal cual a `reports/application/destinatarios.py`, donde ahora son
dos resolutores entre varios en vez de ser *la* regla.

`users` sigue siendo dueño del destinatario y de su bandeja: el usuario tiene
una sola campana, no una por módulo que quiera avisarle algo.

Es **bandeja, no transporte**: la fila se crea siempre y el frontend la
consulta. Empujarla a un teléfono (push, WhatsApp) es una capa aparte que
todavía no existe — y cuando exista, leerá de acá en vez de reemplazarla,
porque un aviso que solo viajó por push no deja rastro de si alguien lo vio.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.users.infrastructure.models import Notificacion


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
    nada (y no es un error: quien resolvió la lista ya lo registró)."""
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
