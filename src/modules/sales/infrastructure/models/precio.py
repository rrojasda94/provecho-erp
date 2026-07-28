"""Precio de un producto comercial dentro de una lista.

Inmutable por diseño: no hay endpoint de edición. Corregir un precio =
lista nueva (RN-PRC-005). Moneda única PEN (RN-PRC-004), por eso no hay
columna de divisa.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Precio(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "precio"
    __table_args__ = (
        UniqueConstraint("lista_precio_id", "producto_comercial_id"),
    )

    lista_precio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lista_precio.id"))
    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
