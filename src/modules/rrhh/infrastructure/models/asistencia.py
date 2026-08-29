"""Asistencia: control de marcaciones (RN-RRHH-009 — no marcado no se
considera). Un trabajador con `registra_asistencia=False` (locación de
servicios, RN-PER-002) no debe tener filas aquí — se valida en `application`."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Asistencia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "asistencia"
    __table_args__ = (
        UniqueConstraint("trabajador_id", "fecha"),
        # El UNIQUE de arriba no sirve para agrupar por fecha entre
        # trabajadores (va segunda): `vw_bi_rrhh_asistencia` (ADR-083) sí
        # lo necesita.
        Index("ix_asistencia_fecha_trabajador", "fecha", "trabajador_id"),
    )

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    fecha: Mapped[date] = mapped_column(Date())
    hora_entrada: Mapped[time | None] = mapped_column(Time(), nullable=True)
    hora_salida: Mapped[time | None] = mapped_column(Time(), nullable=True)
    # Turno de trabajo contra el que se midió la marcación. Nullable: una
    # corrección a mano de RRHH puede no tener turno, y una sucursal puede
    # todavía no tener turnos configurados.
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("turno_sucursal.id"), nullable=True
    )
    tardanza_min: Mapped[int] = mapped_column(default=0)
    # Nunca lo pone el pad: una salida tardía es una salida tardía, no una
    # hora extra (RN-RRHH-022). Solo RRHH lo registra a mano.
    horas_extra: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal(0))
    # Sello del barrido que avisó «falta marcar la salida»: sin esto, cada
    # reintento de la tarea volvería a avisar de lo mismo.
    reporte_salida_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
