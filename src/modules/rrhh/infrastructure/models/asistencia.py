"""Asistencia: control de marcaciones (RN-RRHH-009 — no marcado no se
considera). Un trabajador con `registra_asistencia=False` (locación de
servicios, RN-PER-002) no debe tener filas aquí — se valida en `application`."""

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Asistencia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "asistencia"
    __table_args__ = (UniqueConstraint("trabajador_id", "fecha"),)

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    fecha: Mapped[date] = mapped_column(Date())
    hora_entrada: Mapped[time | None] = mapped_column(Time(), nullable=True)
    hora_salida: Mapped[time | None] = mapped_column(Time(), nullable=True)
    tardanza_min: Mapped[int] = mapped_column(default=0)
    horas_extra: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal(0))
