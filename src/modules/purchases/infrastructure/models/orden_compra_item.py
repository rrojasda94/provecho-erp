import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class OrdenCompraItem(Base, UuidPkMixin):
    __tablename__ = "orden_compra_item"

    orden_compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_compra.id"))
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    # Acumulado de recepciones parciales — nunca > cantidad (RN-CMP-recepción).
    cantidad_recibida: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
