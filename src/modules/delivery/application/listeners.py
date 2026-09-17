"""Listeners de `delivery`: reacciona a hechos de `sales` sin importar su
dominio, y a sus propios hechos para encolar el aviso al cliente y avisar
a caja/cocina (ADR-098/ADR-101).

Cada handler abre su propia sesión (o delega en `tasks.encolar_aviso`, que
abre la suya): el bus despacha después del commit del emisor (ADR-016), así
que la transacción que originó el hecho ya cerró. Un fallo acá no puede
deshacerla, y por eso tampoco se propaga.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.delivery.application import entregas, notificaciones
from src.modules.users.application.queries_publicas import notificar_a, usuarios_con_permiso

log = logging.getLogger(__name__)

# Códigos de `notificacion.tipo` (bandeja in-app) para los avisos de
# caja/cocina del tablero de despacho (ADR-101).
TIPO_ENTREGA_PARA_CAJA = "delivery.entrega_para_cobrar"
TIPO_RUTA_FINALIZADA = "delivery.ruta_finalizada"

# Inyectable (los tests la reemplazan, ver `MODULOS_CON_SESSION_FACTORY` en
# `tests/conftest.py`). Sin esto, cualquier test que anule o entregue una
# venta despertaría este listener contra el Postgres real.
session_factory = SessionLocal

_registrado = False


def on_venta_anulada(payload: dict) -> None:
    """RN-DLV-006: cancela la entrega sola si seguía `pendiente`/`asignada`.
    Si ya estaba `en_ruta`, este handler no la toca — el repartidor puede
    estar a mitad de camino y lo decide el despacho, no un evento."""
    venta_id = uuid.UUID(payload["venta_id"])
    try:
        with session_factory() as session:
            entregas.cancelar_por_venta_anulada(session, venta_id)
            session.commit()
    except Exception:
        log.exception(
            "No se pudo cancelar la entrega tras venta_anulada",
            extra={"venta_id": str(venta_id)},
        )


def on_ruta_iniciada(payload: dict) -> None:
    """El aviso "en camino" es por entrega, no por ruta: cada parada tiene
    su propio cliente y su propio enlace de seguimiento."""
    from src.modules.delivery.application import tasks

    for entrega_id in payload.get("entrega_ids", []):
        try:
            tasks.encolar_aviso(uuid.UUID(entrega_id), notificaciones.EN_CAMINO)
        except Exception:
            log.exception(
                "No se pudo encolar el aviso de en camino", extra={"entrega_id": entrega_id}
            )


def _avisar_a_permisos(
    session: Session,
    *,
    codigos: tuple[str, ...],
    sucursal_id: uuid.UUID,
    tipo: str,
    titulo: str,
    cuerpo: str,
) -> None:
    """Bandeja in-app de todos los que tienen alguno de estos permisos en
    la sucursal — una sola fila por usuario aunque tenga más de un permiso
    de la lista (`set` en vez de notificar por cada uno)."""
    destinatarios: set[uuid.UUID] = set()
    for codigo in codigos:
        destinatarios |= set(usuarios_con_permiso(session, codigo, sucursal_id))
    for usuario_id in destinatarios:
        notificar_a(
            session, usuario_id, tipo=tipo, titulo=titulo, cuerpo=cuerpo, sucursal_id=sucursal_id
        )


def on_entrega_registrada(payload: dict) -> None:
    from src.modules.delivery.application import tasks

    entrega_id = uuid.UUID(payload["entrega_id"])
    try:
        tasks.encolar_aviso(entrega_id, notificaciones.ENTREGADO)
    except Exception:
        log.exception(
            "No se pudo encolar el aviso de entregado", extra={"entrega_id": str(entrega_id)}
        )
    try:
        with session_factory() as session:
            _avisar_a_permisos(
                session,
                codigos=("sales.cobrar",),
                sucursal_id=uuid.UUID(payload["sucursal_id"]),
                tipo=TIPO_ENTREGA_PARA_CAJA,
                titulo="Entrega registrada",
                cuerpo="Un pedido delivery se marcó entregado.",
            )
            session.commit()
    except Exception:
        log.exception(
            "No se pudo avisar a caja de la entrega", extra={"entrega_id": str(entrega_id)}
        )


def on_ruta_finalizada(payload: dict) -> None:
    """Aviso de KDS y caja cuando un repartidor cierra su ruta (ADR-101):
    `delivery.ruta_finalizada` no tenía suscriptores hasta acá."""
    ruta_id = payload["ruta_id"]
    cuerpo = (
        f"{payload.get('entregadas', 0)} entregada(s), {payload.get('fallidas', 0)} fallida(s)."
    )
    try:
        with session_factory() as session:
            _avisar_a_permisos(
                session,
                codigos=("sales.cobrar", "kds.operar"),
                sucursal_id=uuid.UUID(payload["sucursal_id"]),
                tipo=TIPO_RUTA_FINALIZADA,
                titulo="Un repartidor terminó su ruta",
                cuerpo=cuerpo,
            )
            session.commit()
    except Exception:
        log.exception("No se pudo avisar que la ruta terminó", extra={"ruta_id": ruta_id})


def on_entrega_fallida(payload: dict) -> None:
    from src.modules.delivery.application import tasks

    entrega_id = uuid.UUID(payload["entrega_id"])
    try:
        tasks.encolar_aviso(entrega_id, notificaciones.FALLIDA)
    except Exception:
        log.exception(
            "No se pudo encolar el aviso de entrega fallida", extra={"entrega_id": str(entrega_id)}
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_anulada", on_venta_anulada)
    event_bus.subscribe("delivery.ruta_iniciada", on_ruta_iniciada)
    event_bus.subscribe("delivery.entrega_registrada", on_entrega_registrada)
    event_bus.subscribe("delivery.entrega_fallida", on_entrega_fallida)
    event_bus.subscribe("delivery.ruta_finalizada", on_ruta_finalizada)
