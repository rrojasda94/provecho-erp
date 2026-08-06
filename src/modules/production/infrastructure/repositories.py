"""Repositorios SQLAlchemy del módulo production. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.production.infrastructure.models import (
    ConsumoProduccionItem,
    OrdenProduccion,
)

# `Almacen` es organización transversal (data-model §1) y vive en `users`
# por historia: mismo import de modelo que ya hace `application/scope.py`.
from src.modules.users.infrastructure.models import Almacen


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

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        almacen_id: uuid.UUID | None = None,
        estado: str | None = None,
    ):
        """La consulta sin ejecutar: el router la pagina (ADR-026).

        La orden no lleva empresa — la hereda de su almacén, igual que el
        `scope` del módulo (ADR-004).
        """
        q = select(OrdenProduccion)
        if almacen_id is not None:
            q = q.where(OrdenProduccion.almacen_id == almacen_id)
        if estado is not None:
            q = q.where(OrdenProduccion.estado == estado)
        if empresa_id is not None:
            q = q.join(Almacen, Almacen.id == OrdenProduccion.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return q.order_by(OrdenProduccion.created_at.desc())

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
