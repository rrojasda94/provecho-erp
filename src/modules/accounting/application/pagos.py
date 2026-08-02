"""Casos de uso: pago a proveedor (PROC-CTB-003). Compras sustenta el
comprobante conforme (RN-CMP-014); Contabilidad ejecuta el pago, nunca
Compras. `registrar_pago` encola (idempotente por comprobante); `ejecutar_pago`
exige permiso sobre el umbral (RN-CTB-005) y genera el asiento vía
`regla_asiento` (evento `accounting.pago_ejecutado`) — si no hay mapeo
configurado, el pago igual se ejecuta, solo se omite el asiento (se loguea,
un contador lo registra a mano)."""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.accounting.application import asientos as asientos_uc
from src.modules.accounting.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.accounting.domain import rules
from src.modules.accounting.infrastructure.models import MovimientoDinero
from src.modules.accounting.infrastructure.repositories import MovimientoDineroRepo
from src.shared import aprobaciones

log = logging.getLogger(__name__)


def registrar_pago(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    comprobante_id: uuid.UUID | None,
    proveedor_id: uuid.UUID | None = None,
    orden_compra_id: uuid.UUID | None = None,
    monto: Decimal,
    monto_detraccion: Decimal | None = None,
    tipo: str = "egreso",
    concepto: str = "pago_proveedor",
    solicitado_por: uuid.UUID | None = None,
) -> MovimientoDinero:
    """Encola un movimiento de dinero pendiente de ejecución. Idempotente por
    `comprobante_id`: reintentar (ej. el mismo evento publicado dos veces)
    devuelve la fila existente en vez de duplicarla."""
    if monto <= 0:
        raise ReglaNegocio("el monto a pagar debe ser > 0")
    repo = MovimientoDineroRepo(session)
    if comprobante_id is not None:
        existente = repo.get_by_comprobante(comprobante_id)
        if existente is not None:
            return existente
    return repo.add(
        MovimientoDinero(
            empresa_id=empresa_id,
            tipo=tipo,
            concepto=concepto,
            comprobante_id=comprobante_id,
            proveedor_id=proveedor_id,
            orden_compra_id=orden_compra_id,
            monto=monto,
            monto_detraccion=monto_detraccion,
            estado="pendiente",
            solicitado_por=solicitado_por,
        )
    )


def listar_pagos(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[MovimientoDinero]:
    return MovimientoDineroRepo(session).list(empresa_id)


def ejecutar_pago(
    session: Session,
    movimiento_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    puede_aprobar_monto: bool,
    umbral: Decimal,
    medio_pago: str,
    constancia: str | None = None,
) -> MovimientoDinero:
    movimiento = MovimientoDineroRepo(session).get(movimiento_id)
    if movimiento is None:
        raise NoEncontrado("movimiento de dinero no encontrado")
    if not rules.puede_ejecutar_pago(movimiento.estado):
        raise Conflicto(f"el movimiento está {movimiento.estado}; no admite ejecución")
    umbral_efectivo = aprobaciones.umbral_vigente(
        session, movimiento.empresa_id, "accounting", "pago_umbral", default=umbral
    )
    requiere_aprobacion = rules.requiere_aprobacion_pago(movimiento.monto, umbral_efectivo)
    if requiere_aprobacion and not puede_aprobar_monto:
        event_bus.publish(
            "accounting.pago_requiere_aprobacion",
            {
                "movimiento_dinero_id": str(movimiento.id),
                "proveedor_id": str(movimiento.proveedor_id) if movimiento.proveedor_id else None,
                "monto": str(movimiento.monto),
                "umbral": str(umbral_efectivo),
            },
        )
        raise ReglaNegocio(
            f"monto {movimiento.monto} supera el umbral {umbral_efectivo}; "
            "requiere permiso accounting.pago_aprobar"
        )

    movimiento.estado = "ejecutado"
    movimiento.medio_pago = medio_pago
    movimiento.constancia = constancia
    movimiento.aprobado_por = actor_id
    movimiento.fecha_ejecucion = datetime.now()

    asiento = asientos_uc.crear_asiento_automatico_si_hay_regla(
        session,
        empresa_id=movimiento.empresa_id,
        evento="accounting.pago_ejecutado",
        fecha=date.today(),
        glosa=f"Pago a proveedor — movimiento {movimiento.id}",
        referencia_origen=str(movimiento.id),
        monto=movimiento.monto,
    )
    if asiento is not None:
        movimiento.asiento_id = asiento.id
    else:
        log.info(
            "pago %s ejecutado sin asiento: sin regla_asiento para "
            "accounting.pago_ejecutado en empresa %s",
            movimiento.id, movimiento.empresa_id,
        )

    comprobante_id = movimiento.comprobante_id
    orden_compra_id = movimiento.orden_compra_id
    proveedor_id = movimiento.proveedor_id
    monto_detraccion = movimiento.monto_detraccion
    event_bus.publish(
        "accounting.pago_ejecutado",
        {
            "movimiento_dinero_id": str(movimiento.id),
            "comprobante_id": str(comprobante_id) if comprobante_id else None,
            "orden_compra_id": str(orden_compra_id) if orden_compra_id else None,
            "proveedor_id": str(proveedor_id) if proveedor_id else None,
            "monto": str(movimiento.monto),
            "detraccion_monto": str(monto_detraccion) if monto_detraccion else None,
            "aprobado_por": str(actor_id),
        },
    )
    return movimiento


def rechazar_pago(
    session: Session, movimiento_id: uuid.UUID, *, actor_id: uuid.UUID
) -> MovimientoDinero:
    movimiento = MovimientoDineroRepo(session).get(movimiento_id)
    if movimiento is None:
        raise NoEncontrado("movimiento de dinero no encontrado")
    if not rules.puede_rechazar_pago(movimiento.estado):
        raise Conflicto(f"el movimiento está {movimiento.estado}; no admite rechazo")
    movimiento.estado = "rechazado"
    movimiento.aprobado_por = actor_id
    return movimiento
