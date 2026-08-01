"""Qué extras admite cada producto comercial (RN-COM-021).

N:N entre productos: el lado `extra_id` apunta a un `producto_comercial`
con `es_extra=True`. Sin esta tabla el PDV no sabría qué ofrecer al tocar
una pizza, y nada impediría agregarle "extra queso" a una gaseosa.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ProductoComercialExtra(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "producto_comercial_extra"
    __table_args__ = (
        UniqueConstraint(
            "producto_comercial_id", "extra_id", name="uq_producto_extra"
        ),
    )

    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
    # También un `producto_comercial`, pero con `es_extra=True`.
    extra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto_comercial.id"))
    # Tope de unidades del extra en una misma línea (ej. hasta 3 porciones
    # de queso). NULL = sin tope.
    maximo: Mapped[int | None] = mapped_column(Integer, nullable=True)
