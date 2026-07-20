"""Unidad de medida: ratio de conversión respecto a la base de su categoría.

Ej.: Doypack 2kg = ratio 2 sobre Kilo. Un artículo solo admite UdM de su
propia categoría (RN-UDM-001).
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class UnidadMedida(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "unidad_medida"
    __table_args__ = (UniqueConstraint("categoria_udm_id", "nombre"),)

    categoria_udm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categoria_udm.id"))
    nombre: Mapped[str] = mapped_column(String(50))
    ratio: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(1))
