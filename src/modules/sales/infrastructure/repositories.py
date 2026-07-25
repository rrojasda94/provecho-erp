"""Repositorios SQLAlchemy del módulo sales. La sesión es la Unit of Work."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.sales.infrastructure.models import (
    MedioPago,
    Pago,
    ProductoComercial,
    Venta,
    VentaItem,
)


class VentaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, venta_id: uuid.UUID) -> Venta | None:
        return self.s.get(Venta, venta_id)

    def get_by_idempotency(self, key: str) -> Venta | None:
        return self.s.scalar(select(Venta).where(Venta.idempotency_key == key))

    def siguiente_numero_orden(self, sucursal_id: uuid.UUID, fecha: date) -> int:
        actual = self.s.scalar(
            select(func.max(Venta.numero_orden)).where(
                Venta.sucursal_id == sucursal_id, Venta.fecha_orden == fecha
            )
        )
        return (actual or 0) + 1

    def add(self, venta: Venta) -> Venta:
        self.s.add(venta)
        self.s.flush()
        return venta

    def items(self, venta_id: uuid.UUID) -> list[VentaItem]:
        return list(
            self.s.scalars(select(VentaItem).where(VentaItem.venta_id == venta_id))
        )


class PagoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_by_idempotency(self, key: str) -> Pago | None:
        return self.s.scalar(select(Pago).where(Pago.idempotency_key == key))

    def add(self, pago: Pago) -> Pago:
        self.s.add(pago)
        self.s.flush()
        return pago

    def confirmados(self, venta_id: uuid.UUID) -> list[Decimal]:
        return list(
            self.s.scalars(
                select(Pago.monto).where(
                    Pago.venta_id == venta_id, Pago.estado == "confirmado"
                )
            )
        )


class ProductoComercialRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, producto_id: uuid.UUID) -> ProductoComercial | None:
        return self.s.get(ProductoComercial, producto_id)

    def get_by_id_interno(self, id_interno: str) -> ProductoComercial | None:
        return self.s.scalar(
            select(ProductoComercial).where(
                ProductoComercial.id_interno == id_interno
            )
        )

    def list(self, marca_id: uuid.UUID | None = None) -> list[ProductoComercial]:
        q = select(ProductoComercial).where(ProductoComercial.activo.is_(True))
        if marca_id is not None:
            q = q.where(ProductoComercial.marca_id == marca_id)
        return list(self.s.scalars(q.order_by(ProductoComercial.nombre)))

    def add(self, producto: ProductoComercial) -> ProductoComercial:
        self.s.add(producto)
        self.s.flush()
        return producto


class MedioPagoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, medio_pago_id: uuid.UUID) -> MedioPago | None:
        return self.s.get(MedioPago, medio_pago_id)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[MedioPago]:
        q = select(MedioPago).where(MedioPago.activo.is_(True))
        if empresa_id is not None:
            q = q.where(MedioPago.empresa_id == empresa_id)
        return list(self.s.scalars(q))

    def add(self, medio: MedioPago) -> MedioPago:
        self.s.add(medio)
        self.s.flush()
        return medio
