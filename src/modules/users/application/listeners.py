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
from src.modules.users.infrastructure.models import Almacen

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


def _avisar_al_almacen(
    almacen_id: uuid.UUID,
    *,
    tipo: str,
    nivel: str,
    titulo: str,
    cuerpo: str,
    referencia_tipo: str,
    referencia_id: uuid.UUID,
) -> None:
    """Forma común de los tres avisos de inventario: cambia el texto, no la
    mecánica. `sucursal_id` va desde el almacén cuando lo tiene, para que la
    bandeja pueda filtrar por local; el central no tiene y va en NULL."""
    with SessionLocal() as session:
        destinatarios = notificaciones.destinatarios_de_almacen(session, almacen_id)
        almacen = session.get(Almacen, almacen_id)
        notificaciones.notificar(
            session,
            destinatarios,
            tipo=tipo,
            nivel=nivel,
            titulo=titulo,
            cuerpo=cuerpo,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            sucursal_id=almacen.sucursal_id if almacen else None,
        )
        session.commit()


def on_stock_bajo_minimo(payload: dict) -> None:
    """El SKU acaba de cruzar su mínimo. `aviso` y no `urgente`: todavía hay
    stock, lo que falta es reponer antes de que no lo haya."""
    _avisar_al_almacen(
        uuid.UUID(payload["almacen_id"]),
        tipo="inventory.stock_bajo_minimo",
        nivel="aviso",
        titulo=f"Stock bajo mínimo: quedan {payload['cantidad']}",
        cuerpo=f"El mínimo configurado es {payload['stock_minimo']}. Hay que reponer.",
        referencia_tipo="sku",
        referencia_id=uuid.UUID(payload["sku_id"]),
    )


def on_lote_vencido_detectado(payload: dict) -> None:
    """Un lote vencido seguía disponible y quedó bloqueado.

    `urgente` porque el stock ya se contaba como vendible: alguien pudo
    haberlo servido. El memorándum al responsable (RN-VNC) sigue pendiente y
    no por falta de aviso — `almacen` no tiene responsable modelado, así que
    no hay a quién dirigirlo; esto avisa al rol, que es lo que se puede hoy.
    """
    _avisar_al_almacen(
        uuid.UUID(payload["almacen_id"]),
        tipo="inventory.lote_vencido_detectado",
        nivel="urgente",
        titulo=f"Lote vencido bloqueado: {payload['cantidad']} en stock",
        cuerpo=(
            f"Venció el {payload['fecha_vencimiento']} y seguía disponible. "
            "Ya no puede salir; hay que darlo de baja."
        ),
        referencia_tipo="lote",
        referencia_id=uuid.UUID(payload["lote_id"]),
    )


def on_conteo_vencido(payload: dict) -> None:
    """Una categoría no se contó en la fecha que su frecuencia exigía
    (RN-INV-021). Se repite cada día hasta que se cuente: es un
    recordatorio, no la noticia de un evento."""
    _avisar_al_almacen(
        uuid.UUID(payload["almacen_id"]),
        tipo="inventory.conteo_vencido",
        nivel="aviso",
        titulo=f"Conteo atrasado: {payload['categoria']} ({payload['dias_atraso']} d)",
        cuerpo=(
            f"Frecuencia {payload['frecuencia']}; tocaba el "
            f"{payload['fecha_programada']}."
        ),
        referencia_tipo="categoria",
        referencia_id=uuid.UUID(payload["categoria_id"]),
    )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.pedido_demorado", on_pedido_demorado)
    event_bus.subscribe("inventory.stock_bajo_minimo", on_stock_bajo_minimo)
    event_bus.subscribe(
        "inventory.lote_vencido_detectado", on_lote_vencido_detectado
    )
    event_bus.subscribe("inventory.conteo_vencido", on_conteo_vencido)
