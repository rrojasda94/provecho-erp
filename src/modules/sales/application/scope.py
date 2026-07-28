"""Validación de alcance de tenant sobre recursos de sales (ADR-004).

La sucursal de una venta manda: el usuario solo ve/toca ventas de las
sucursales que su JWT le asigna.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.sales.application.errors import NoEncontrado
from src.modules.sales.infrastructure.models import (
    KdsPantalla,
    Venta,
    VentaItem,
)


def exigir_venta(session: Session, venta_id: uuid.UUID, tenant: Tenant) -> Venta:
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    tenant.exigir_sucursal(venta.sucursal_id)
    return venta


def exigir_pantalla(
    session: Session, pantalla_id: uuid.UUID, tenant: Tenant
) -> KdsPantalla:
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None or pantalla.deleted_at is not None:
        raise NoEncontrado("pantalla no encontrada")
    tenant.exigir_sucursal(pantalla.sucursal_id)
    return pantalla


def exigir_venta_item(
    session: Session, venta_item_id: uuid.UUID, tenant: Tenant
) -> VentaItem:
    item = session.get(VentaItem, venta_item_id)
    if item is None:
        raise NoEncontrado("ítem de venta no encontrado")
    exigir_venta(session, item.venta_id, tenant)
    return item
