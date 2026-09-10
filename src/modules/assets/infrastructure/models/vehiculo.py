"""Vehículo: extiende `activo` 1:1 (data-model.md §Recursos, RN-VEH-001..004).

`flota` queda diferida (ver `activo.py`): el vehículo hoy no la referencia.
"""

import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin
from src.modules.assets.domain.rules import TENENCIAS_VEHICULO, TIPOS_VEHICULO


class Vehiculo(Base, TimestampMixin):
    __tablename__ = "vehiculo"

    __table_args__ = (
        CheckConstraint(
            "tipo_vehiculo IN ('moto', 'auto', 'camioneta', 'camion', 'otro')",
            name="tipo_vehiculo",
        ),
        CheckConstraint("tenencia IN ('propio', 'alquilado')", name="tenencia_vehiculo"),
    )

    activo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activo.id"), primary_key=True)
    # Único a secas y no por empresa: la placa es un registro nacional, no
    # algo que dos empresas del grupo puedan compartir de verdad. Mismo largo
    # que `guia_remision.vehiculo_placa`: cuando exista flota propia con
    # tracking, esa columna se reemplaza por esta FK (ADR-027).
    placa: Mapped[str] = mapped_column(String(10), unique=True)
    tipo_vehiculo: Mapped[str] = mapped_column(
        Enum(*TIPOS_VEHICULO, name="tipo_vehiculo", native_enum=False)
    )
    numero_motor: Mapped[str | None] = mapped_column(String(40), nullable=True)
    numero_chasis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tenencia: Mapped[str] = mapped_column(
        Enum(*TENENCIAS_VEHICULO, name="tenencia_vehiculo", native_enum=False),
        default="propio",
    )
    # Última lectura conocida (RN-VEH-004). Cache de la última fila de
    # `lectura_odometro`: leerlo no debería obligar a agregar sobre el
    # historial completo cada vez que se arma la ficha.
    kilometraje_actual: Mapped[int | None] = mapped_column(nullable=True)
