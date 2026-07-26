"""Casos de uso de nómina: `boleta_pago` (RN-RRHH-001) y `liquidacion_bss`
(RN-RRHH-003). Operaciones de dinero → idempotentes."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.rrhh.application.errors import NoEncontrado
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import BoletaPago, LiquidacionBss
from src.modules.rrhh.infrastructure.repositories import (
    BoletaPagoRepo,
    LiquidacionBssRepo,
    TrabajadorRepo,
)


def emitir_boleta_pago(
    session: Session,
    *,
    trabajador_id: uuid.UUID,
    periodo: str,
    dias_laborados: int,
    remuneracion: Decimal,
    ingresos: dict,
    descuentos: dict,
    aportes_empleador: Decimal,
    neto_pagar: Decimal,
    fecha_pago: date,
    idempotency_key: str,
) -> BoletaPago:
    repo = BoletaPagoRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente
    if TrabajadorRepo(session).get(trabajador_id) is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")

    boleta = repo.add(
        BoletaPago(
            trabajador_id=trabajador_id,
            periodo=periodo,
            dias_laborados=dias_laborados,
            remuneracion=remuneracion,
            ingresos=ingresos,
            descuentos=descuentos,
            aportes_empleador=aportes_empleador,
            neto_pagar=neto_pagar,
            fecha_pago=fecha_pago,
            idempotency_key=idempotency_key,
        )
    )
    event_bus.publish(
        "rrhh.boleta_pago_emitida",
        {
            "boleta_pago_id": str(boleta.id),
            "trabajador_id": str(trabajador_id),
            "periodo": periodo,
            "neto_pagar": str(neto_pagar),
        },
    )
    return boleta


def liquidar_cese(
    session: Session,
    *,
    trabajador_id: uuid.UUID,
    cts_pendiente: Decimal = Decimal(0),
    vacaciones_truncas: Decimal = Decimal(0),
    gratificacion_trunca: Decimal = Decimal(0),
    otros_adeudos: Decimal = Decimal(0),
    fecha_pago: date,
    idempotency_key: str,
) -> LiquidacionBss:
    repo = LiquidacionBssRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")
    if trabajador.fecha_cese is None:
        raise NoEncontrado("trabajador no tiene fecha_cese registrada")

    total = cts_pendiente + vacaciones_truncas + gratificacion_trunca + otros_adeudos
    dentro_de_plazo = rules.dentro_de_plazo_horas(trabajador.fecha_cese, fecha_pago)

    liquidacion = repo.add(
        LiquidacionBss(
            trabajador_id=trabajador_id,
            fecha_cese=trabajador.fecha_cese,
            cts_pendiente=cts_pendiente,
            vacaciones_truncas=vacaciones_truncas,
            gratificacion_trunca=gratificacion_trunca,
            otros_adeudos=otros_adeudos,
            total=total,
            fecha_pago=fecha_pago,
            dentro_de_plazo=dentro_de_plazo,
            idempotency_key=idempotency_key,
        )
    )
    event_bus.publish(
        "rrhh.liquidacion_bss_pagada",
        {
            "liquidacion_bss_id": str(liquidacion.id),
            "trabajador_id": str(trabajador_id),
            "total": str(total),
            "dentro_de_plazo": dentro_de_plazo,
        },
    )
    return liquidacion
