"""Validación de alcance de tenant sobre recursos de sales (ADR-004).

La sucursal de una venta manda: el usuario solo ve/toca ventas de las
sucursales que su JWT le asigna.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import FueraDeAlcance, Tenant
from src.modules.sales.application import clientes
from src.modules.sales.application.errors import NoEncontrado
from src.modules.sales.infrastructure.models import (
    Cliente,
    KdsPantalla,
    Mesa,
    Venta,
    VentaItem,
)


def exigir_cliente(session: Session, cliente_id: uuid.UUID, tenant: Tenant) -> Cliente:
    """El cliente es del **grupo**, no de la empresa (RN-PTS-001), así que el
    alcance se valida contra el grupo de la empresa del token — no con
    `tenant.exigir_empresa`, que aquí no aplica.

    Un superusuario sin empresa asignada pasa: es el mismo criterio que el
    resto del ERP para la cuenta de administración.
    """
    cliente = session.get(Cliente, cliente_id)
    if cliente is None or cliente.deleted_at is not None:
        raise NoEncontrado("cliente no encontrado")
    if tenant.superusuario and tenant.empresa_id is None:
        return cliente
    grupo_id = clientes.grupo_de_empresa(session, tenant.empresa())
    if cliente.grupo_id != grupo_id:
        raise FueraDeAlcance("cliente fuera del alcance del usuario")
    return cliente


def exigir_venta(session: Session, venta_id: uuid.UUID, tenant: Tenant) -> Venta:
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    tenant.exigir_sucursal(venta.sucursal_id)
    return venta


def exigir_mesa(session: Session, mesa_id: uuid.UUID, tenant: Tenant) -> Mesa:
    mesa = session.get(Mesa, mesa_id)
    if mesa is None:
        raise NoEncontrado("mesa no encontrada")
    tenant.exigir_sucursal(mesa.sucursal_id)
    return mesa


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
