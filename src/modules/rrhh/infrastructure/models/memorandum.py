"""Memorándum: comunicación interna (no es sanción por sí — distinto de
`amonestacion`, RN-RRHH-010)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Memorandum(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "memorandum"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    emisor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Destinatario es un trabajador puntual o un área — excluyentes.
    destinatario_trabajador_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trabajador.id"), nullable=True
    )
    destinatario_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asunto: Mapped[str] = mapped_column(String(200))
    cuerpo: Mapped[str] = mapped_column(Text())
    fecha: Mapped[date] = mapped_column(Date())
