"""Línea de una recepción de compra: qué llegó y en qué condiciones.

El lote y el vencimiento son **lo que declaró el proveedor** (RN-VNC-002) y
se guardan acá, en el documento de recepción, además de viajar en
`purchases.compra_recibida` hacia `inventory`. Antes solo viajaban: si el
listener fallaba, el dato del lote se perdía y no quedaba dónde leerlo para
reprocesar ni con qué contrastar el lote que `inventory` terminó creando.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class RecepcionItem(Base, UuidPkMixin):
    __tablename__ = "recepcion_item"

    recepcion_compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recepcion_compra.id"))
    orden_compra_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_compra_item.id"))
    cantidad_recibida: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    # NULL cuando el artículo no controla lote, o cuando el proveedor no
    # declaró nada y el ERP derivó el lote del día.
    lote_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
