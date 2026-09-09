"""Listeners de `production` a eventos de otros módulos.

El README del módulo decía "Escucha: `inventory.stock_bajo_minimo` (dispara
orden por necesidad, RN-PRD-007)" desde 2026-07-25 y nunca se cumplió — el
evento se publica, pero nada del lado de `production` lo consumía. Este es
el primer listener del módulo.

Un fallo acá NUNCA rompe el flujo de `inventory` que cruzó el mínimo: el
handler atrapa y loguea, igual criterio que `inventory.application.
listeners`.
"""

import logging
import uuid
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.inventory.infrastructure.models import Articulo, Receta, Sku
from src.modules.production.application import reposicion
from src.modules.production.application.errors import AppError
from src.modules.production.application.ordenes import crear_orden_produccion
from src.modules.production.infrastructure.repositories import OrdenProduccionRepo
from src.modules.users.infrastructure.models import Almacen
from src.shared import fechas

log = logging.getLogger("provecho.production.listeners")

session_factory = SessionLocal


def on_stock_bajo_minimo(payload: dict) -> None:
    try:
        with session_factory() as session:
            _crear_orden_por_necesidad(session, payload)
            session.commit()
    except AppError:
        # No hay nada roto: una regla de negocio (idempotency_key repetida
        # por un reintento del propio bus, por ejemplo) decidió no crear
        # nada. Es el resultado esperado, no un fallo que loguear.
        pass
    except Exception:
        log.exception(
            "fallo creando la orden por necesidad del SKU %s", payload.get("sku_id")
        )


def _crear_orden_por_necesidad(session: Session, payload: dict) -> None:
    sku = session.get(Sku, uuid.UUID(payload["sku_id"]))
    if sku is None:
        return
    articulo = session.get(Articulo, sku.articulo_id)
    if articulo is None:
        return
    receta = session.scalar(select(Receta).where(Receta.articulo_id == articulo.id))
    if receta is None or not receta.rendimiento_cantidad:
        return  # no es una subreceta con BOM: nada que producir

    almacen_origen = session.get(Almacen, uuid.UUID(payload["almacen_id"]))
    if almacen_origen is None:
        return
    # Solo si la empresa tiene **una** cocina de producción: con cero no hay
    # a dónde mandarla, y con más de una no hay forma de elegir sin que
    # alguien lo decida (RN-PRD-007/011) — el aviso sigue viéndose en
    # `reports`, que es donde Gerencia decide a mano en esos casos.
    almacenes_produccion = list(
        session.scalars(
            select(Almacen).where(
                Almacen.empresa_id == almacen_origen.empresa_id,
                Almacen.tipo == "produccion",
                Almacen.deleted_at.is_(None),
            )
        )
    )
    if len(almacenes_produccion) != 1:
        return
    almacen_produccion = almacenes_produccion[0]

    if OrdenProduccionRepo(session).abierta_de(articulo.id, almacen_produccion.id):
        return  # ya hay una orden de este artículo sin cerrar control de calidad

    cantidad = Decimal(payload["cantidad"])
    stock_minimo = Decimal(payload["stock_minimo"])
    factor = reposicion.factor_reposicion_de(session, almacen_origen.empresa_id)
    deficit = stock_minimo * factor - cantidad
    if deficit <= 0:
        return

    # Redondeado al rendimiento de la receta: la cocina produce en lotes
    # completos, no una fracción de tanda.
    rendimiento = receta.rendimiento_cantidad
    lotes = (deficit / rendimiento).to_integral_value(rounding=ROUND_CEILING)
    cantidad_planeada = lotes * rendimiento

    crear_orden_produccion(
        session,
        articulo_id=articulo.id,
        almacen_id=almacen_produccion.id,
        cantidad_planeada=cantidad_planeada,
        creado_por=None,
        idempotency_key=f"necesidad:{sku.id}:{fechas.hoy().isoformat()}",
        origen="ajuste_por_necesidad",
    )


_registrado = False


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("inventory.stock_bajo_minimo", on_stock_bajo_minimo)
