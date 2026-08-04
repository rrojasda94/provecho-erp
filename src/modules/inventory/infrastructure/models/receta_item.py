"""Ítem de receta: un artículo (insumo/subreceta) con cantidad y merma.

La cantidad se expresa en la unidad de medida del propio artículo
(`articulo.unidad_medida_id`): la receta no elige unidad, la hereda del
insumo que usa. Por eso no hay columna de UdM acá — habría dos fuentes para
el mismo dato y la del artículo es la que manda en el descuento de stock.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class RecetaItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "receta_item"

    receta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receta.id"))
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    merma_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(0))
    # Lo que el usuario tecleó si la cantidad salió de una operación
    # ("1000/3"). Se guarda para poder reeditarla, no para recalcularla: la
    # verdad es `cantidad`, ya redondeada a los decimales de la UdM.
    expresion: Mapped[str | None] = mapped_column(String(60), nullable=True)
