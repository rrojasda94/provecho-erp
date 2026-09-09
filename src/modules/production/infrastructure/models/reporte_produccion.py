"""Reporte de producción de la jornada (RN-DOC-010): se genera solo con lo
que la cocina fue registrando durante el día — el jefe de cocina lo visa,
no lo redacta. Único por `(almacen_id, jornada)`: `application/
reportes_jornada.py::generar_reporte_jornada` recalcula el existente
mientras no esté visado, y deja de tocarlo en cuanto lo está.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class ReporteProduccion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "reporte_produccion"

    __table_args__ = (UniqueConstraint("almacen_id", "jornada"),)

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    jornada: Mapped[date] = mapped_column(Date)
    generado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Snapshot de las órdenes completadas ese día: [{orden_produccion_id,
    # articulo_id, estado, cantidad_producida, costo_real_unitario,
    # merma_cantidad, horas_hombre}]. No se relee de `orden_produccion` una
    # vez generado — es la foto de la jornada, no una vista en vivo.
    ordenes: Mapped[list] = mapped_column(JsonB, default=list)
    merma_total: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    desperdicio_total: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    horas_hombre_total: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal(0))
    costo_total: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    # Nullable: sin visar todavía. Un solo timestamp además del actor —igual
    # criterio que `reports.ReporteEscalamiento.cerrado_at`— porque acá sí
    # hace falta saber además quién, para RN-DOC-010 ("visado por el
    # encargado o jefe de cocina responsable").
    visado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    visado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String(1000), nullable=True)
