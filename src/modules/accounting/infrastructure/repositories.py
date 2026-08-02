"""Repositorios del módulo accounting: la sesión es la Unit of Work, el
repositorio solo encapsula queries."""

# `AsientoRepo` define un método `list`, que dentro del cuerpo de la clase
# pisa el builtin `list` — sin esto, la anotación `-> list[AsientoLinea]` de
# `lineas` (definida después) revienta con "'function' object is not
# subscriptable" en Python <3.14 (evaluación eager de anotaciones). Con este
# import las anotaciones quedan como string y nunca se evalúan así.
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.accounting.infrastructure.models import (
    AperturaCaja,
    Arqueo,
    Asiento,
    AsientoLinea,
    CierreCaja,
    CuentaContable,
    MovimientoCaja,
    MovimientoDinero,
    PeriodoContable,
    ReglaAsiento,
)


class CuentaContableRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, cuenta_id: uuid.UUID) -> CuentaContable | None:
        return self.s.get(CuentaContable, cuenta_id)

    def get_by_codigo(self, empresa_id: uuid.UUID, codigo: str) -> CuentaContable | None:
        return self.s.scalar(
            select(CuentaContable).where(
                CuentaContable.empresa_id == empresa_id,
                CuentaContable.codigo == codigo,
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[CuentaContable]:
        q = select(CuentaContable).where(CuentaContable.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(CuentaContable.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(CuentaContable.codigo)))

    def add(self, cuenta: CuentaContable) -> CuentaContable:
        self.s.add(cuenta)
        self.s.flush()
        return cuenta


class PeriodoContableRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, periodo_id: uuid.UUID) -> PeriodoContable | None:
        return self.s.get(PeriodoContable, periodo_id)

    def get_by_anio_mes(self, empresa_id: uuid.UUID, anio: int, mes: int) -> PeriodoContable | None:
        return self.s.scalar(
            select(PeriodoContable).where(
                PeriodoContable.empresa_id == empresa_id,
                PeriodoContable.anio == anio,
                PeriodoContable.mes == mes,
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[PeriodoContable]:
        q = select(PeriodoContable)
        if empresa_id is not None:
            q = q.where(PeriodoContable.empresa_id == empresa_id)
        return list(
            self.s.scalars(q.order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc()))
        )

    def add(self, periodo: PeriodoContable) -> PeriodoContable:
        self.s.add(periodo)
        self.s.flush()
        return periodo


class AsientoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, asiento_id: uuid.UUID) -> Asiento | None:
        return self.s.get(Asiento, asiento_id)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Asiento]:
        q = select(Asiento)
        if empresa_id is not None:
            q = q.where(Asiento.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(Asiento.fecha.desc())))

    def lineas(self, asiento_id: uuid.UUID) -> list[AsientoLinea]:
        return list(
            self.s.scalars(select(AsientoLinea).where(AsientoLinea.asiento_id == asiento_id))
        )

    def existe_por_origen(
        self, empresa_id: uuid.UUID, evento: str, referencia_origen: str
    ) -> bool:
        return (
            self.s.scalar(
                select(Asiento.id).where(
                    Asiento.empresa_id == empresa_id,
                    Asiento.evento_origen == evento,
                    Asiento.referencia_origen == referencia_origen,
                )
            )
            is not None
        )

    def add(self, asiento: Asiento) -> Asiento:
        self.s.add(asiento)
        self.s.flush()
        return asiento


class ReglaAsientoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, regla_id: uuid.UUID) -> ReglaAsiento | None:
        return self.s.get(ReglaAsiento, regla_id)

    def get_vigente(self, empresa_id: uuid.UUID, evento: str) -> ReglaAsiento | None:
        return self.s.scalar(
            select(ReglaAsiento).where(
                ReglaAsiento.empresa_id == empresa_id,
                ReglaAsiento.evento == evento,
                ReglaAsiento.activa.is_(True),
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[ReglaAsiento]:
        q = select(ReglaAsiento)
        if empresa_id is not None:
            q = q.where(ReglaAsiento.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(ReglaAsiento.evento)))

    def add(self, regla: ReglaAsiento) -> ReglaAsiento:
        self.s.add(regla)
        self.s.flush()
        return regla


class MovimientoDineroRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, movimiento_id: uuid.UUID) -> MovimientoDinero | None:
        return self.s.get(MovimientoDinero, movimiento_id)

    def get_by_comprobante(self, comprobante_id: uuid.UUID) -> MovimientoDinero | None:
        return self.s.scalar(
            select(MovimientoDinero).where(MovimientoDinero.comprobante_id == comprobante_id)
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[MovimientoDinero]:
        q = select(MovimientoDinero)
        if empresa_id is not None:
            q = q.where(MovimientoDinero.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(MovimientoDinero.created_at.desc())))

    def add(self, movimiento: MovimientoDinero) -> MovimientoDinero:
        self.s.add(movimiento)
        self.s.flush()
        return movimiento


class AperturaCajaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, apertura_id: uuid.UUID) -> AperturaCaja | None:
        return self.s.get(AperturaCaja, apertura_id)

    def abierta_en(self, punto_venta_id: uuid.UUID) -> AperturaCaja | None:
        """La apertura vigente de ese punto de venta: la más reciente que
        todavía no tiene `cierre_caja`."""
        return self.s.scalar(
            select(AperturaCaja)
            .outerjoin(CierreCaja, CierreCaja.apertura_caja_id == AperturaCaja.id)
            .where(AperturaCaja.punto_venta_id == punto_venta_id, CierreCaja.id.is_(None))
            .order_by(AperturaCaja.created_at.desc())
        )

    def abiertas_de(self, punto_venta_ids: list[uuid.UUID]) -> list[AperturaCaja]:
        if not punto_venta_ids:
            return []
        return list(
            self.s.scalars(
                select(AperturaCaja)
                .outerjoin(CierreCaja, CierreCaja.apertura_caja_id == AperturaCaja.id)
                .where(
                    AperturaCaja.punto_venta_id.in_(punto_venta_ids),
                    CierreCaja.id.is_(None),
                )
            )
        )

    def add(self, apertura: AperturaCaja) -> AperturaCaja:
        self.s.add(apertura)
        self.s.flush()
        return apertura


class MovimientoCajaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_by_idempotency(self, key: str) -> MovimientoCaja | None:
        return self.s.scalar(
            select(MovimientoCaja).where(MovimientoCaja.idempotency_key == key)
        )

    def de_apertura(self, apertura_caja_id: uuid.UUID) -> list[MovimientoCaja]:
        return list(
            self.s.scalars(
                select(MovimientoCaja)
                .where(MovimientoCaja.apertura_caja_id == apertura_caja_id)
                .order_by(MovimientoCaja.created_at)
            )
        )

    def neto(self, apertura_caja_id: uuid.UUID) -> Decimal:
        """Ingresos menos retiros. Es lo que hay que sumarle al esperado del
        cierre para que cuadre contra el cajón real."""
        total = Decimal(0)
        for mov in self.de_apertura(apertura_caja_id):
            total += mov.monto if mov.tipo == "ingreso" else -mov.monto
        return total

    def add(self, movimiento: MovimientoCaja) -> MovimientoCaja:
        self.s.add(movimiento)
        self.s.flush()
        return movimiento


class CierreCajaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_by_apertura(self, apertura_caja_id: uuid.UUID) -> CierreCaja | None:
        return self.s.scalar(
            select(CierreCaja).where(CierreCaja.apertura_caja_id == apertura_caja_id)
        )

    def add(self, cierre: CierreCaja) -> CierreCaja:
        self.s.add(cierre)
        self.s.flush()
        return cierre


class ArqueoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def list(self, punto_venta_id: uuid.UUID) -> list[Arqueo]:
        return list(
            self.s.scalars(
                select(Arqueo)
                .where(Arqueo.punto_venta_id == punto_venta_id)
                .order_by(Arqueo.created_at.desc())
            )
        )

    def add(self, arqueo: Arqueo) -> Arqueo:
        self.s.add(arqueo)
        self.s.flush()
        return arqueo
