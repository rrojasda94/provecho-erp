"""Arqueo: verificación puntual de caja fuera del ciclo apertura/cierre
(sorpresa o programado)."""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Arqueo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "arqueo"

    punto_venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("punto_venta.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("sorpresa", "programado", name="tipo_arqueo", native_enum=False)
    )
    realizado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    monto_esperado: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    monto_contado: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    diferencia: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    # Referencia a `acta` — entidad aún no modelada (RRHH/documentos).
    acta_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
