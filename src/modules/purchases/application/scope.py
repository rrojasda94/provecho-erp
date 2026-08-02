"""Validación de alcance de tenant sobre recursos de purchases (ADR-004).

El proveedor lleva el `empresa_id`; la orden de compra hereda el alcance de
su proveedor. El cliente nunca elige la empresa: se deriva del JWT.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.purchases.application.errors import NoEncontrado
from src.modules.purchases.infrastructure.models import OrdenCompra, Proveedor
from src.modules.users.infrastructure.models import Almacen


def exigir_almacen(session: Session, almacen_id: uuid.UUID, tenant: Tenant) -> Almacen:
    almacen = session.get(Almacen, almacen_id)
    if almacen is None or almacen.deleted_at is not None:
        raise NoEncontrado("almacén no encontrado")
    tenant.exigir_empresa(almacen.empresa_id)
    return almacen


def exigir_proveedor(
    session: Session, proveedor_id: uuid.UUID, tenant: Tenant
) -> Proveedor:
    proveedor = session.get(Proveedor, proveedor_id)
    if proveedor is None or proveedor.deleted_at is not None:
        raise NoEncontrado("proveedor no encontrado")
    tenant.exigir_empresa(proveedor.empresa_id)
    return proveedor


def exigir_orden_compra(
    session: Session, orden_compra_id: uuid.UUID, tenant: Tenant
) -> OrdenCompra:
    orden = session.get(OrdenCompra, orden_compra_id)
    if orden is None:
        raise NoEncontrado("orden de compra no encontrada")
    exigir_proveedor(session, orden.proveedor_id, tenant)
    return orden
