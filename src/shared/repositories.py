"""Repositorio de entidades transversales de `shared`. Mismo patrón que los
repos de módulo: la sesión es la Unit of Work, el repo solo encapsula queries.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.models import ReglaAprobacion


class ReglaAprobacionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, regla_id: uuid.UUID) -> ReglaAprobacion | None:
        return self.s.get(ReglaAprobacion, regla_id)

    def get_vigente(
        self, empresa_id: uuid.UUID, modulo: str, codigo: str
    ) -> ReglaAprobacion | None:
        return self.s.scalar(
            select(ReglaAprobacion).where(
                ReglaAprobacion.empresa_id == empresa_id,
                ReglaAprobacion.modulo == modulo,
                ReglaAprobacion.codigo == codigo,
                ReglaAprobacion.vigente.is_(True),
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[ReglaAprobacion]:
        stmt = select(ReglaAprobacion)
        if empresa_id is not None:
            stmt = stmt.where(ReglaAprobacion.empresa_id == empresa_id)
        return list(self.s.scalars(stmt.order_by(ReglaAprobacion.modulo, ReglaAprobacion.codigo)))

    def add(self, regla: ReglaAprobacion) -> ReglaAprobacion:
        self.s.add(regla)
        self.s.flush()
        return regla
