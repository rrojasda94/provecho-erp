"""Listeners de `delivery`: reacciona a hechos de `sales` sin importar su
dominio (ADR-098).

Cada handler abre su propia sesión: el bus despacha después del commit del
emisor (ADR-016), así que la transacción que originó el hecho ya cerró. Un
fallo acá no puede deshacerla, y por eso tampoco se propaga.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.delivery.application import entregas

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


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_entregada", on_venta_entregada)
    event_bus.subscribe("sales.venta_anulada", on_venta_anulada)
