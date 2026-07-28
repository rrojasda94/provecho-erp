"""Validación de alcance de tenant sobre recursos de inventory (ADR-004).

El `empresa_id` nunca viene del cliente: se deriva del JWT y aquí se
contrasta contra el recurso que el request dice tocar.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.inventory.application.errors import NoEncontrado
from src.modules.inventory.infrastructure.models import Ajuste, Articulo, Lote
from src.modules.users.infrastructure.models import Almacen


def exigir_almacen(session: Session, almacen_id: uuid.UUID, tenant: Tenant) -> Almacen:
    almacen = session.get(Almacen, almacen_id)
    if almacen is None or almacen.deleted_at is not None:
        raise NoEncontrado("almacén no encontrado")
    tenant.exigir_empresa(almacen.empresa_id)
    return almacen


def exigir_articulo(
    session: Session, articulo_id: uuid.UUID, tenant: Tenant
) -> Articulo:
    articulo = session.get(Articulo, articulo_id)
    if articulo is None or articulo.deleted_at is not None:
        raise NoEncontrado("artículo no encontrado")
    tenant.exigir_empresa(articulo.empresa_id)
    return articulo


def exigir_lote(session: Session, lote_id: uuid.UUID, tenant: Tenant) -> Lote:
    lote = session.get(Lote, lote_id)
    if lote is None:
        raise NoEncontrado("lote no encontrado")
    exigir_articulo(session, lote.articulo_id, tenant)
    return lote


def exigir_ajuste(session: Session, ajuste_id: uuid.UUID, tenant: Tenant) -> Ajuste:
    ajuste = session.get(Ajuste, ajuste_id)
    if ajuste is None:
        raise NoEncontrado("ajuste no encontrado")
    exigir_almacen(session, ajuste.almacen_id, tenant)
    return ajuste
