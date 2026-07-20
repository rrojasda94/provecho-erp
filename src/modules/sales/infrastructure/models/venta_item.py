"""Ítem de venta: producto comercial, cantidad y precio al momento de
vender (snapshot — no depende de lista_precio para existir).
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class VentaItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "venta_item"

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"))
    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    descuento: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
