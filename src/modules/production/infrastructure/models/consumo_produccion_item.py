"""Detalle de insumos realmente consumidos por una orden — contrastado
contra `receta_item.merma_pct` (esperado) para medir desperdicio real."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class ConsumoProduccionItem(Base, UuidPkMixin):
    __tablename__ = "consumo_produccion_item"

    orden_produccion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_produccion.id"))
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    peso_desperdicio_real: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    tipo_desperdicio: Mapped[str | None] = mapped_column(String(50), nullable=True)
