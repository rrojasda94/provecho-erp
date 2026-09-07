"""Periodo contable: unidad mensual de cierre (RN-CTB-002/006)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class PeriodoContable(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "periodo_contable"
    __table_args__ = (
        UniqueConstraint("empresa_id", "anio", "mes"),
        CheckConstraint(
            "estado IN ('abierto', 'cerrado')",
            name="estado_periodo_contable",
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    anio: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(
        Enum("abierto", "cerrado", name="estado_periodo_contable", native_enum=False),
        default="abierto",
    )
    cerrado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    fecha_cierre: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
