"""Validación de alcance de tenant sobre recursos de accounting (ADR-004).

Los recursos contables (cuenta, periodo, asiento, pago) llevan `empresa_id`
directo. Los de caja cuelgan de un punto de venta, así que su alcance es el
de la sucursal de ese punto de venta — resuelto vía el contrato público de
`sales`, nunca importando su dominio (CLAUDE.md).
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.accounting.application.errors import NoEncontrado
from src.modules.accounting.infrastructure.models import (
    AperturaCaja,
    Asiento,
    CuentaContable,
    MovimientoDinero,
    PeriodoContable,
)
from src.modules.sales.application.queries_publicas import sucursal_de_punto_venta


def exigir_punto_venta(
    session: Session, punto_venta_id: uuid.UUID, tenant: Tenant
) -> None:
    sucursal_id = sucursal_de_punto_venta(session, punto_venta_id)
    if sucursal_id is None:
        raise NoEncontrado("punto de venta no encontrado")
    tenant.exigir_sucursal(sucursal_id)


def exigir_cuenta(
    session: Session, cuenta_id: uuid.UUID, tenant: Tenant
) -> CuentaContable:
    cuenta = session.get(CuentaContable, cuenta_id)
    if cuenta is None or cuenta.deleted_at is not None:
        raise NoEncontrado("cuenta contable no encontrada")
    tenant.exigir_empresa(cuenta.empresa_id)
    return cuenta


def exigir_periodo(
    session: Session, periodo_id: uuid.UUID, tenant: Tenant
) -> PeriodoContable:
    periodo = session.get(PeriodoContable, periodo_id)
    if periodo is None:
        raise NoEncontrado("periodo contable no encontrado")
    tenant.exigir_empresa(periodo.empresa_id)
    return periodo


def exigir_asiento(session: Session, asiento_id: uuid.UUID, tenant: Tenant) -> Asiento:
    asiento = session.get(Asiento, asiento_id)
    if asiento is None:
        raise NoEncontrado("asiento no encontrado")
    tenant.exigir_empresa(asiento.empresa_id)
    return asiento


def exigir_pago(
    session: Session, movimiento_id: uuid.UUID, tenant: Tenant
) -> MovimientoDinero:
    movimiento = session.get(MovimientoDinero, movimiento_id)
    if movimiento is None:
        raise NoEncontrado("movimiento de dinero no encontrado")
    tenant.exigir_empresa(movimiento.empresa_id)
    return movimiento


def exigir_apertura_caja(
    session: Session, apertura_caja_id: uuid.UUID, tenant: Tenant
) -> AperturaCaja:
    apertura = session.get(AperturaCaja, apertura_caja_id)
    if apertura is None:
        raise NoEncontrado("apertura de caja no encontrada")
    exigir_punto_venta(session, apertura.punto_venta_id, tenant)
    return apertura
