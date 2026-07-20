"""Ítem de receta: un artículo (insumo/subreceta) con cantidad y merma."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class RecetaItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "receta_item"

    receta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receta.id"))
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    merma_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(0))
