"""Listeners de `delivery`: reacciona a hechos de `sales` sin importar su
dominio, y a sus propios hechos para encolar el aviso al cliente (ADR-098).

Cada handler abre su propia sesión (o delega en `tasks.encolar_aviso`, que
abre la suya): el bus despacha después del commit del emisor (ADR-016), así
que la transacción que originó el hecho ya cerró. Un fallo acá no puede
deshacerla, y por eso tampoco se propaga.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.delivery.application import entregas, notificaciones

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan, ver `MODULOS_CON_SESSION_FACTORY` en
# `tests/conftest.py`). Sin esto, cualquier test que anule o entregue una
# venta despertaría este listener contra el Postgres real.
session_factory = SessionLocal

_registrado = False


def on_venta_entregada(payload: dict) -> None:
    """Si la venta se marcó entregada desde el KDS (no desde el tablero de
    reparto), cierra la `entrega` abierta que le quedó colgando — los dos
    caminos convergen sin que ninguno conozca el dominio del otro."""
    venta_id = uuid.UUID(payload["venta_id"])
    entregado_por = payload.get("entregado_por")
    try:
        with session_factory() as session:
            entregas.cerrar_por_venta_entregada(
                session,
                venta_id,
                entregado_por=uuid.UUID(entregado_por) if entregado_por else None,
            )
            session.commit()
    except Exception:
        log.exception(
            "No se pudo cerrar la entrega tras venta_entregada",
            extra={"venta_id": str(venta_id)},
        )


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


def on_entrega_registrada(payload: dict) -> None:
    from src.modules.delivery.application import tasks

    entrega_id = uuid.UUID(payload["entrega_id"])
    try:
        tasks.encolar_aviso(entrega_id, notificaciones.ENTREGADO)
    except Exception:
        log.exception(
            "No se pudo encolar el aviso de entregado", extra={"entrega_id": str(entrega_id)}
        )


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
    event_bus.subscribe("sales.venta_entregada", on_venta_entregada)
    event_bus.subscribe("sales.venta_anulada", on_venta_anulada)
    event_bus.subscribe("delivery.ruta_iniciada", on_ruta_iniciada)
    event_bus.subscribe("delivery.entrega_registrada", on_entrega_registrada)
    event_bus.subscribe("delivery.entrega_fallida", on_entrega_fallida)
