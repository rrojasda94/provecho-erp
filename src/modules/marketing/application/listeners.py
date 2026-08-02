"""Listener: `sales.venta_confirmada` → atribución lead→venta.

Solo atribuye cuando **no hay ambigüedad**: el cliente tiene exactamente un
lead abierto en una campaña en curso. Con dos o más, adivinar cuál campaña
se lleva el crédito falsearía la medición de conversión — esos casos quedan
para la atribución manual (`POST /marketing/leads/{id}/atribucion`).

Nunca bloquea la venta: cualquier fallo se loguea, mismo criterio que
`inventory`/`accounting`.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.marketing.infrastructure.repositories import LeadRepo

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan), mismo patrón que los otros módulos.
session_factory = SessionLocal


def on_venta_confirmada(payload: dict) -> None:
    cliente_id = payload.get("cliente_id")
    if not cliente_id:
        return
    try:
        with session_factory() as session:
            abiertos = LeadRepo(session).sin_atribuir_de_cliente(uuid.UUID(cliente_id))
            if len(abiertos) != 1:
                if abiertos:
                    log.info(
                        "venta %s: %s leads abiertos del cliente, atribución manual",
                        payload.get("venta_id"),
                        len(abiertos),
                    )
                return
            abiertos[0].venta_id = uuid.UUID(payload["venta_id"])
            session.commit()
    except Exception:
        log.exception("fallo atribuyendo lead de la venta %s", payload.get("venta_id"))


_registrado = False


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_confirmada", on_venta_confirmada)
