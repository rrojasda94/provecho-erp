"""Validación de alcance de tenant sobre recursos de production (ADR-004).

La orden de producción se escopa por su almacén: `almacen.empresa_id` es el
tenant efectivo de la orden.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.production.application.errors import NoEncontrado
from src.modules.production.infrastructure.models import OrdenProduccion
from src.modules.users.infrastructure.models import Almacen


def exigir_almacen(session: Session, almacen_id: uuid.UUID, tenant: Tenant) -> Almacen:
    almacen = session.get(Almacen, almacen_id)
    if almacen is None or almacen.deleted_at is not None:
        raise NoEncontrado("almacén no encontrado")
    tenant.exigir_empresa(almacen.empresa_id)
    return almacen


def exigir_orden(
    session: Session, orden_id: uuid.UUID, tenant: Tenant
) -> OrdenProduccion:
    orden = session.get(OrdenProduccion, orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    exigir_almacen(session, orden.almacen_id, tenant)
    return orden
