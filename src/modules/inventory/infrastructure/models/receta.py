"""Receta: BOM de un producto comercial o de una subreceta.

`producto_comercial.receta_id` la usa como BOM de venta directa;
`articulo_id` (aquí) la liga como BOM de una subreceta — cuando está
seteado, `production` la resuelve para saber qué consume una orden que
produce ese artículo (RN-PRD). Una receta sirve a uno u otro uso, no a
ambos a la vez.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Receta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "receta"

    nombre: Mapped[str] = mapped_column(String(150))
    rendimiento_cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    rendimiento_unidad_medida_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("unidad_medida.id")
    )
    flexible: Mapped[bool] = mapped_column(Boolean, default=False)
    # Solo si flexible=True, lo asigna Producción (RN-PRD-010).
    criterio_ajuste: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Subreceta que esta receta produce (tipo `subreceta` en `articulo`) —
    # nullable: NULL si la receta es de un producto_comercial de venta directa.
    articulo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("articulo.id"), nullable=True
    )
