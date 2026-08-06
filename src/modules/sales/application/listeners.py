"""Listeners de `sales`.

Hoy uno solo: al confirmarse una venta se programa la revisión de demora
para dentro del umbral. El listener **no revisa nada** — encola y vuelve.
El bus es síncrono y en proceso (`core/events.py`): bloquear acá esperando
15 minutos congelaría la caja que confirmó la venta.
"""

import logging

from src.core.events import event_bus

log = logging.getLogger(__name__)

_registrado = False


def on_venta_confirmada(payload: dict) -> None:
    """Programa la revisión de demora del pedido recién enviado a cocina.

    La importación va adentro para no arrastrar Celery (ni su broker) al
    importar este módulo: los tests del dominio no levantan Redis.
    """
    from src.modules.sales.application import tasks

    venta_id = payload["venta_id"]
    try:
        tasks.programar_revision_demora(venta_id)
    except Exception:
        # Que la cola esté caída no puede tumbar la venta: ya está cobrada y
        # el pedido salió a cocina. El barrido periódico lo levanta igual —
        # para eso existe.
        log.exception(
            "No se pudo programar la revisión de demora", extra={"venta_id": venta_id}
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_confirmada", on_venta_confirmada)
