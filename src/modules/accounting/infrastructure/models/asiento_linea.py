"""Línea de asiento: debe/haber. La suma de líneas de un asiento siempre
cuadra (RN-CTB-001), validado en `domain.rules.cuadra` antes de persistir."""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class AsientoLinea(Base, UuidPkMixin):
    __tablename__ = "asiento_linea"

    asiento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asiento.id"))
    cuenta_contable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta_contable.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("debe", "haber", name="tipo_linea_asiento", native_enum=False)
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
