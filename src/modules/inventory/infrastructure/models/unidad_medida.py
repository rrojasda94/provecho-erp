"""Unidad de medida: ratio de conversión respecto a la base de su categoría.

Ej.: Doypack 2kg = ratio 2 sobre Kilo. Un artículo solo admite UdM de su
propia categoría (RN-UDM-001).

`decimales` define con cuánta precisión se expresa una cantidad en esta
unidad: 3 para kilos (gramos importan), 0 para unidades sueltas (media
botella no existe). Es configuración de la unidad, no una constante del
código (RN-GER-010).
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class UnidadMedida(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "unidad_medida"
    __table_args__ = (UniqueConstraint("categoria_udm_id", "nombre"),)

    categoria_udm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categoria_udm.id"))
    nombre: Mapped[str] = mapped_column(String(50))
    ratio: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(1))
    decimales: Mapped[int] = mapped_column(Integer, default=3)
