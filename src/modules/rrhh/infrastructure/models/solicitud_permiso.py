"""Solicitud de permiso: vacaciones/licencia/permiso, sujeta a aprobación
(RN-RRHH-005). Entidad `solicitud` genérica aún no existe en código — se
modela directo en `rrhh`, mismo diferimiento que `contrato_laboral`."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class SolicitudPermiso(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "solicitud_permiso"

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    tipo: Mapped[str] = mapped_column(
        Enum(
            "vacaciones", "licencia_con_goce", "licencia_sin_goce", "permiso_horas",
            name="tipo_solicitud_permiso", native_enum=False,
        )
    )
    fecha_desde: Mapped[date] = mapped_column(Date())
    fecha_hasta: Mapped[date | None] = mapped_column(Date(), nullable=True)
    # Solo si tipo=permiso_horas.
    horas: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text(), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "pendiente", "aprobada", "rechazada",
            name="estado_solicitud_permiso", native_enum=False,
        ),
        default="pendiente",
    )
    aprobador_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
