"""stock: cantidad actual por almacén/SKU. Cache derivable de
`movimiento_inventario` — nunca se edita directo, solo vía movimientos.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Stock(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "stock"
    __table_args__ = (UniqueConstraint("almacen_id", "sku_id"),)

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    # Punto de reorden (RN-INV-013). Alerta al llegar a stock_minimo.
    stock_minimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    stock_maximo: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
