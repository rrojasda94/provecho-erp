"""Repuestos consumidos al realizar una orden de mantenimiento.

`nombre_articulo` congela el nombre al momento de consumir: el repuesto de
`inventory` puede renombrarse o darse de baja después sin que la orden
pierda sentido (mismo criterio que direcciones/tarifas congeladas en otros
módulos).
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class OrdenMantenimientoRepuesto(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "orden_mantenimiento_repuesto"

    orden_mantenimiento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_mantenimiento.id"))
    # Sin FK: `articulo` es dominio de `inventory`.
    articulo_id: Mapped[uuid.UUID] = mapped_column()
    nombre_articulo: Mapped[str] = mapped_column(String(120))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    costo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
