"""Listeners de `storefront`: cierra el enlace cuenta↔cliente (ADR-102) y el
resultado de un pedido web confirmado (ADR-103).

`sales` escucha `storefront.cuenta_registrada`/`storefront.pedido_web_
confirmado` y publica de vuelta `sales.cliente_vinculado`/`sales.pedido_web_
procesado` cuando termina — este módulo nunca importa `sales.application.*`,
solo reacciona a esos eventos.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.storefront.infrastructure.repositories import CuentaRepo, PedidoRepo

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


def on_pedido_web_procesado(payload: dict) -> None:
    """`sales` terminó de convertir (o rechazar) el pedido en una `Venta`
    real — acá solo se refleja el resultado en la fila que el cliente ya
    está mirando en `/pedido/{id}`."""
    pedido_id = uuid.UUID(payload["pedido_id"])
    try:
        with session_factory() as session:
            pedido = PedidoRepo(session).get(pedido_id)
            if pedido is None:
                return
            if payload.get("ok"):
                pedido.estado = "confirmado"
                pedido.venta_id = uuid.UUID(payload["venta_id"])
                pedido.numero_orden = payload.get("numero_orden")
            else:
                pedido.estado = "fallido"
                pedido.fallo_motivo = payload.get("motivo") or "no se pudo confirmar"
            session.commit()
    except Exception:
        log.exception(
            "No se pudo actualizar el estado del pedido web",
            extra={"pedido_id": str(pedido_id)},
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.cliente_vinculado", on_cliente_vinculado)
    event_bus.subscribe("sales.pedido_web_procesado", on_pedido_web_procesado)
