"""Repositorios SQLAlchemy del módulo production. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.production.infrastructure.models import (
    ConsumoProduccionItem,
    OrdenProduccion,
)


class OrdenProduccionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, orden_id: uuid.UUID) -> OrdenProduccion | None:
        return self.s.get(OrdenProduccion, orden_id)

    def get_by_idempotency(self, idempotency_key: str) -> OrdenProduccion | None:
        return self.s.scalar(
            select(OrdenProduccion).where(
                OrdenProduccion.idempotency_key == idempotency_key
            )
        )

    def add(self, orden: OrdenProduccion) -> OrdenProduccion:
        self.s.add(orden)
        self.s.flush()
        return orden

    def consumos(self, orden_id: uuid.UUID) -> list[ConsumoProduccionItem]:
        return list(
            self.s.scalars(
                select(ConsumoProduccionItem).where(
                    ConsumoProduccionItem.orden_produccion_id == orden_id
                )
            )
        )
