"""Repositorios SQLAlchemy del módulo purchases. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.purchases.infrastructure.models import (
    OrdenCompra,
    OrdenCompraItem,
    Proveedor,
    RecepcionCompra,
    RecepcionItem,
)
from src.modules.users.infrastructure.models import Almacen


class ProveedorRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, proveedor_id: uuid.UUID) -> Proveedor | None:
        return self.s.get(Proveedor, proveedor_id)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Proveedor]:
        q = select(Proveedor).where(Proveedor.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Proveedor.empresa_id == empresa_id)
        return list(self.s.scalars(q))

    def add(self, proveedor: Proveedor) -> Proveedor:
        self.s.add(proveedor)
        self.s.flush()
        return proveedor


class OrdenCompraRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, orden_compra_id: uuid.UUID) -> OrdenCompra | None:
        return self.s.get(OrdenCompra, orden_compra_id)

    def get_by_idempotency(self, idempotency_key: str) -> OrdenCompra | None:
        return self.s.scalar(
            select(OrdenCompra).where(OrdenCompra.idempotency_key == idempotency_key)
        )

    def items(self, orden_compra_id: uuid.UUID) -> list[OrdenCompraItem]:
        return list(
            self.s.scalars(
                select(OrdenCompraItem).where(
                    OrdenCompraItem.orden_compra_id == orden_compra_id
                )
            )
        )

    def add(self, orden: OrdenCompra) -> OrdenCompra:
        self.s.add(orden)
        self.s.flush()
        return orden

    def list(self, empresa_id: uuid.UUID | None = None) -> list[OrdenCompra]:
        # `orden_compra` no tiene empresa_id propio — el tenant sale de su
        # almacén destino (mismo patrón que `application/scope.py`).
        stmt = select(OrdenCompra).order_by(OrdenCompra.created_at.desc())
        if empresa_id is not None:
            stmt = stmt.join(Almacen, Almacen.id == OrdenCompra.almacen_destino_id).where(
                Almacen.empresa_id == empresa_id
            )
        return list(self.s.scalars(stmt))


class RecepcionCompraRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_by_idempotency(self, idempotency_key: str) -> RecepcionCompra | None:
        return self.s.scalar(
            select(RecepcionCompra).where(
                RecepcionCompra.idempotency_key == idempotency_key
            )
        )

    def add(self, recepcion: RecepcionCompra) -> RecepcionCompra:
        self.s.add(recepcion)
        self.s.flush()
        return recepcion

    def items(self, recepcion_compra_id: uuid.UUID) -> list[RecepcionItem]:
        return list(
            self.s.scalars(
                select(RecepcionItem).where(
                    RecepcionItem.recepcion_compra_id == recepcion_compra_id
                )
            )
        )

    def ultima_de_orden(self, orden_compra_id: uuid.UUID) -> RecepcionCompra | None:
        return self.s.scalar(
            select(RecepcionCompra)
            .where(RecepcionCompra.orden_compra_id == orden_compra_id)
            .order_by(RecepcionCompra.fecha.desc())
        )
