"""Repositorio de entidades transversales de `shared`. Mismo patrón que los
repos de módulo: la sesión es la Unit of Work, el repo solo encapsula queries.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.models import Divisa, ParametroEmpresa


class DivisaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_por_codigo(self, codigo: str) -> Divisa | None:
        return self.s.scalar(
            select(Divisa).where(Divisa.codigo == codigo, Divisa.activa.is_(True))
        )

    def list(self) -> list[Divisa]:
        return list(self.s.scalars(select(Divisa).order_by(Divisa.codigo)))


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
