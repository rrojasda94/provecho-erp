"""Pacto de permanencia por capacitación: razonable y proporcional en plazo
y monto de reembolso (RN-RRHH-006) — el reembolso es proporcional al tiempo
de permanencia no cumplido."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class PactoPermanencia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "pacto_permanencia"

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    capacitacion_descripcion: Mapped[str] = mapped_column(String(255))
    capacitacion_tipo: Mapped[str] = mapped_column(
        Enum(
            "curso", "posgrado", "diplomado", "capacitacion",
            name="tipo_capacitacion_pacto", native_enum=False,
        )
    )
    costo_financiado: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    plazo_permanencia_meses: Mapped[int] = mapped_column()
    fecha_inicio: Mapped[date] = mapped_column(Date())
    fecha_fin_compromiso: Mapped[date] = mapped_column(Date())
