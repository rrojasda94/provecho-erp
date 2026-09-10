"""Listeners de `sales`.

Al confirmarse una venta se programa la revisión de demora para dentro del
umbral — ese handler **no revisa nada**, encola y vuelve, porque el bus es
síncrono y en proceso (`core/events.py`) y bloquear acá esperando 15
minutos congelaría la caja que confirmó la venta.

El segundo handler (`delivery.entrega_registrada`) sí abre su propia
sesión: es la mitad `sales` del cierre de la rama delivery de
`PROC-OPE-002` (ADR-098) — `delivery` nunca importa `cumplimiento`
directamente, publica el evento y este handler hace la llamada real.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan, ver `MODULOS_CON_SESSION_FACTORY` en
# `tests/conftest.py`). Solo lo usa `on_entrega_registrada`: el handler de
# `venta_confirmada` no toca la base, así que sembrarlo acá no le costaba
# nada a los tests hasta que este segundo handler lo hizo necesario.
session_factory = SessionLocal

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


def on_entrega_registrada(payload: dict) -> None:
    """`delivery` registró la entrega de una venta: se marca entregada acá,
    con la misma `cumplimiento.registrar_entrega` que usa el botón
    "Entregar" del KDS (ADR-098) — mismo camino, mismo idempotente
    (RN-CUP-005), sin que `sales` sepa que existe `delivery`.

    `entregado_por` es el `repartidor_usuario_id` del payload y no quien
    tocó el botón en el celular: RN-CUP-007 pide registrar **quién
    entrega**, y eso es el repartidor, aunque lo haya confirmado despacho
    en su nombre.

    Fallar acá no deshace la entrega ya registrada en `delivery` (ADR-016,
    entrega best-effort en proceso): queda una venta sin marcar hasta que
    alguien la entregue a mano desde el KDS. Se documenta como costo
    aceptado en `events.md`, no se reintenta desde acá.
    """
    from src.modules.sales.application import cumplimiento

    venta_id = uuid.UUID(payload["venta_id"])
    entregado_por = uuid.UUID(payload["repartidor_usuario_id"])
    try:
        with session_factory() as session:
            cumplimiento.registrar_entrega(session, venta_id, entregado_por=entregado_por)
            session.commit()
    except Exception:
        log.exception(
            "No se pudo marcar entregada la venta de una entrega de delivery",
            extra={"venta_id": str(venta_id)},
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_confirmada", on_venta_confirmada)
    event_bus.subscribe("delivery.entrega_registrada", on_entrega_registrada)
