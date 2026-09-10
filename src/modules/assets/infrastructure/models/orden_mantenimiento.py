"""Orden de mantenimiento: ejecución de un plan o adelanto por avería
(RN-MNT-002/003/004)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.modules.assets.domain.rules import (
    ESTADOS_ORDEN_MANTENIMIENTO,
    MOTIVOS_ADELANTO,
    TIPOS_ORDEN_MANTENIMIENTO,
)


class OrdenMantenimiento(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "orden_mantenimiento"

    __table_args__ = (
        CheckConstraint("tipo IN ('programado', 'adelantado')", name="tipo_orden_mantenimiento"),
        CheckConstraint(
            "motivo_adelanto IS NULL OR motivo_adelanto IN ('desperfecto', 'baja_productividad')",
            name="motivo_adelanto_orden",
        ),
        CheckConstraint(
            "estado IN ('programada', 'en_curso', 'realizada', 'cancelada')",
            name="estado_orden_mantenimiento",
        ),
    )

    activo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activo.id"))
    # Nulo si nace de un reporte de avería y no de un plan (RN-MNT-003).
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plan_mantenimiento.id"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(
        Enum(*TIPOS_ORDEN_MANTENIMIENTO, name="tipo_orden_mantenimiento", native_enum=False)
    )
    motivo_adelanto: Mapped[str | None] = mapped_column(
        Enum(*MOTIVOS_ADELANTO, name="motivo_adelanto_orden", native_enum=False),
        nullable=True,
    )
    fecha_programada: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_realizada: Mapped[date | None] = mapped_column(Date, nullable=True)
    km_al_realizar: Mapped[int | None] = mapped_column(nullable=True)
    # Sin FK: `proveedor` es dominio de `purchases`.
    proveedor_servicio_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # RN-MNT-004: a quién se dirige el reporte que adelanta el mantenimiento.
    reportado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    resultado: Mapped[str | None] = mapped_column(Text, nullable=True)
    costo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    comprobante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comprobante.id"), unique=True, nullable=True
    )
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS_ORDEN_MANTENIMIENTO, name="estado_orden_mantenimiento", native_enum=False),
        default="programada",
    )
