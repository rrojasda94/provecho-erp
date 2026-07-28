"""stock_lote: detalle por lote de la cantidad que `stock` totaliza.

`stock.cantidad` sigue siendo la cifra que consultan el dashboard y el
PDV; para un artículo con `controla_lote`, la suma de sus `stock_lote`
disponibles/bloqueados cuadra con ella (ADR-015).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

ESTADO_STOCK_LOTE = Enum(
    "disponible",
    "bloqueado",
    "agotado",
    name="estado_stock_lote",
    native_enum=False,
)


class StockLote(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "stock_lote"
    __table_args__ = (UniqueConstraint("almacen_id", "sku_id", "lote_id"),)

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    # `bloqueado` = vencido o retenido: no lo toma el picking (RN-VNC-001..003).
    estado: Mapped[str] = mapped_column(ESTADO_STOCK_LOTE, default="disponible")
