"""Repositorios del módulo accounting: la sesión es la Unit of Work, el
repositorio solo encapsula queries."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.accounting.infrastructure.models import (
    Asiento,
    AsientoLinea,
    CuentaContable,
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

    def list(self, empresa_id: uuid.UUID) -> list[CuentaContable]:
        return list(
            self.s.scalars(
                select(CuentaContable)
                .where(CuentaContable.empresa_id == empresa_id, CuentaContable.deleted_at.is_(None))
                .order_by(CuentaContable.codigo)
            )
        )

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

    def list(self, empresa_id: uuid.UUID) -> list[PeriodoContable]:
        return list(
            self.s.scalars(
                select(PeriodoContable)
                .where(PeriodoContable.empresa_id == empresa_id)
                .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
            )
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

    def list(self, empresa_id: uuid.UUID) -> list[Asiento]:
        return list(
            self.s.scalars(
                select(Asiento)
                .where(Asiento.empresa_id == empresa_id)
                .order_by(Asiento.fecha.desc())
            )
        )

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

    def list(self, empresa_id: uuid.UUID) -> list[ReglaAsiento]:
        return list(
            self.s.scalars(
                select(ReglaAsiento)
                .where(ReglaAsiento.empresa_id == empresa_id)
                .order_by(ReglaAsiento.evento)
            )
        )

    def add(self, regla: ReglaAsiento) -> ReglaAsiento:
        self.s.add(regla)
        self.s.flush()
        return regla
