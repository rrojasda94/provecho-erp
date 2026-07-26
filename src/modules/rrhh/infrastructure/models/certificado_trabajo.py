"""Certificado de trabajo: se emite al cese dentro de 48 h (RN-RRHH-002)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class CertificadoTrabajo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "certificado_trabajo"

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    fecha_emision: Mapped[date] = mapped_column(Date())
    tiempo_servicios_meses: Mapped[int] = mapped_column()
    cargos: Mapped[str] = mapped_column(String(255))
    # Solo a solicitud del trabajador (RN-RRHH-002).
    conducta_desempeno: Mapped[str | None] = mapped_column(Text(), nullable=True)
    dentro_de_plazo: Mapped[bool] = mapped_column(Boolean, default=True)
