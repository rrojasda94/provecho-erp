"""Listeners de `users`: convierte hechos de otros módulos en avisos.

`users` es el dueño del destinatario, así que es el que sabe a quién
avisarle. Los módulos que publican el hecho no conocen ni al encargado de
turno ni la bandeja — publican qué pasó y siguen.

Cada handler abre **su propia sesión**: el bus despacha después del commit
del emisor (`core/events.py`), así que la transacción que originó el hecho
ya cerró. Un fallo acá no puede deshacerla, y por eso tampoco se propaga.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.users.application import notificaciones

log = logging.getLogger("provecho.app")

_registrado = False


def on_pedido_demorado(payload: dict) -> None:
    """Avisa al encargado de turno que un pedido lleva demasiado en cocina."""
    sucursal_id = uuid.UUID(payload["sucursal_id"])
    minutos = payload["minutos_transcurridos"]
    umbral = payload["minutos_umbral"]
    estado = payload["estado"]

    detalle = (
        "Cocina todavía no lo empezó."
        if estado == "pendiente"
        else "Sigue en preparación."
    )

    with SessionLocal() as session:
        destinatarios = notificaciones.destinatarios_de_sucursal(session, sucursal_id)
        notificaciones.notificar(
            session,
            destinatarios,
            tipo="sales.pedido_demorado",
            # `urgente` cuando cocina ni lo empezó: es el caso en que
            # alguien tiene que ir a la cocina, no solo enterarse.
            nivel="urgente" if estado == "pendiente" else "aviso",
            titulo=f"Pedido demorado: {float(minutos):.0f} min (límite {umbral})",
            cuerpo=f"{detalle} Ítems pendientes: {payload['items_pendientes']}.",
            referencia_tipo="venta",
            referencia_id=uuid.UUID(payload["venta_id"]),
            sucursal_id=sucursal_id,
        )
        session.commit()


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.pedido_demorado", on_pedido_demorado)
