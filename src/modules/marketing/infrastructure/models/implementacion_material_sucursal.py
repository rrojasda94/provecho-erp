"""Verificación en sitio del material de campaña en una sucursal: enviar el
material no cierra la tarea (RN-MKT-005)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.shared import fechas


class ImplementacionMaterialSucursal(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "implementacion_material_sucursal"
    __table_args__ = (UniqueConstraint("campana_id", "sucursal_id", "fecha"),)

    campana_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campana.id"))
    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    fecha: Mapped[date] = mapped_column(Date, default=fechas.hoy)
    verificado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Completa = producto nuevo y clásico, no solo el lanzamiento.
    completa: Mapped[bool] = mapped_column(Boolean, default=False)
    incidencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
