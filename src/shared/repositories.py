"""Repositorio de entidades transversales de `shared`. Mismo patrón que los
repos de módulo: la sesión es la Unit of Work, el repo solo encapsula queries.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.models import DecisionGerencial, Divisa, ParametroEmpresa


class DecisionGerencialRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, decision_id: uuid.UUID) -> DecisionGerencial | None:
        return self.s.get(DecisionGerencial, decision_id)

    def list(
        self,
        empresa_id: uuid.UUID | None = None,
        referencia_tipo: str | None = None,
        referencia_id: uuid.UUID | None = None,
        tipo: str | None = None,
    ) -> list[DecisionGerencial]:
        stmt = select(DecisionGerencial).where(DecisionGerencial.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(DecisionGerencial.empresa_id == empresa_id)
        if referencia_tipo is not None:
            stmt = stmt.where(DecisionGerencial.referencia_tipo == referencia_tipo)
        if referencia_id is not None:
            stmt = stmt.where(DecisionGerencial.referencia_id == referencia_id)
        if tipo is not None:
            stmt = stmt.where(DecisionGerencial.tipo == tipo)
        return list(
            self.s.scalars(stmt.order_by(DecisionGerencial.fecha.desc()))
        )

    def add(self, decision: DecisionGerencial) -> DecisionGerencial:
        self.s.add(decision)
        self.s.flush()
        return decision


class DivisaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, divisa_id: uuid.UUID) -> Divisa | None:
        return self.s.get(Divisa, divisa_id)

    def get_por_codigo(self, codigo: str) -> Divisa | None:
        return self.s.scalar(
            select(Divisa).where(Divisa.codigo == codigo, Divisa.activa.is_(True))
        )

    def list(self) -> list[Divisa]:
        return list(self.s.scalars(select(Divisa).order_by(Divisa.codigo)))

    def add(self, divisa: Divisa) -> Divisa:
        self.s.add(divisa)
        self.s.flush()
        return divisa


class ParametroEmpresaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, parametro_id: uuid.UUID) -> ParametroEmpresa | None:
        return self.s.get(ParametroEmpresa, parametro_id)

    def get_vigente(
        self, empresa_id: uuid.UUID, modulo: str, codigo: str
    ) -> ParametroEmpresa | None:
        return self.s.scalar(
            select(ParametroEmpresa).where(
                ParametroEmpresa.empresa_id == empresa_id,
                ParametroEmpresa.modulo == modulo,
                ParametroEmpresa.codigo == codigo,
                ParametroEmpresa.estado == "vigente",
            )
        )

    def list(
        self,
        empresa_id: uuid.UUID | None = None,
        estado: str | None = None,
        modulo: str | None = None,
    ) -> list[ParametroEmpresa]:
        stmt = select(ParametroEmpresa)
        if empresa_id is not None:
            stmt = stmt.where(ParametroEmpresa.empresa_id == empresa_id)
        if estado is not None:
            stmt = stmt.where(ParametroEmpresa.estado == estado)
        if modulo is not None:
            stmt = stmt.where(ParametroEmpresa.modulo == modulo)
        return list(
            self.s.scalars(
                stmt.order_by(ParametroEmpresa.modulo, ParametroEmpresa.codigo)
            )
        )

    def add(self, parametro: ParametroEmpresa) -> ParametroEmpresa:
        self.s.add(parametro)
        self.s.flush()
        return parametro
