"""Línea de una devolución: qué SKU, cuánto y de qué lote.

El lote importa: la razón más común para devolver es que algo venció o vino
dañado, y eso siempre es **un lote concreto**. Sin él, la salida la elegiría
FEFO y sacaría el lote equivocado — justamente el que sí servía.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class DevolucionItem(Base, UuidPkMixin):
    __tablename__ = "devolucion_item"

    devolucion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devolucion.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    # NULL si el artículo no controla lote.
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lote.id"), nullable=True
    )
