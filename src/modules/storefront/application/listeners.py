"""Listeners de `storefront`: cierra el enlace cuenta↔cliente (ADR-102).

`sales` escucha `storefront.cuenta_registrada` y publica de vuelta
`sales.cliente_vinculado` cuando termina — este módulo nunca importa
`sales.application.clientes`, solo reacciona al segundo evento.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.storefront.infrastructure.repositories import CuentaRepo

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan, ver `MODULOS_CON_SESSION_FACTORY` en
# `tests/conftest.py`).
session_factory = SessionLocal

_registrado = False


def on_cliente_vinculado(payload: dict) -> None:
    cuenta_id = uuid.UUID(payload["cuenta_id"])
    cliente_id = uuid.UUID(payload["cliente_id"])
    try:
        with session_factory() as session:
            cuenta = CuentaRepo(session).get(cuenta_id)
            if cuenta is None:
                return
            cuenta.cliente_id = cliente_id
            session.commit()
    except Exception:
        log.exception(
            "No se pudo guardar el cliente_id vinculado a la cuenta",
            extra={"cuenta_id": str(cuenta_id)},
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.cliente_vinculado", on_cliente_vinculado)
