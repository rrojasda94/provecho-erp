"""Lectura de odómetro: historial de kilometraje de un vehículo (RN-VEH-004,
RN-VEH-005). La registra directamente un usuario, o la genera una carga de
combustible o una orden de mantenimiento que trae km."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.modules.assets.domain.rules import ORIGENES_LECTURA


class LecturaOdometro(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "lectura_odometro"

    __table_args__ = (
        CheckConstraint(
            "origen IN ('manual', 'carga_combustible', 'mantenimiento')",
            name="origen_lectura_odometro",
        ),
    )

    vehiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehiculo.activo_id"))
    fecha: Mapped[date] = mapped_column(Date)
    km: Mapped[int] = mapped_column()
    origen: Mapped[str] = mapped_column(
        Enum(*ORIGENES_LECTURA, name="origen_lectura_odometro", native_enum=False)
    )
    registrado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
