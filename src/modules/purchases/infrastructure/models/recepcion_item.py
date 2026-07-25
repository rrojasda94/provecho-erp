import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class RecepcionItem(Base, UuidPkMixin):
    __tablename__ = "recepcion_item"

    recepcion_compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recepcion_compra.id"))
    orden_compra_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_compra_item.id"))
    cantidad_recibida: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 4))
