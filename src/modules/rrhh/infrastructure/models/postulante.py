"""Postulante: candidato en proceso de selección, antes de convertirse en
`trabajador`. Datos (CV, contacto) sujetos a consentimiento previo
(RN-PER-004, Ley 29733)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Postulante(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "postulante"

    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persona.id"))
    puesto_postulado: Mapped[str] = mapped_column(String(150))
    fecha_postulacion: Mapped[date] = mapped_column(Date())
    # RN-PER-004: consentimiento previo, informado y expreso.
    consentimiento_datos: Mapped[bool] = mapped_column(Boolean, default=False)
    consentimiento_fecha: Mapped[date | None] = mapped_column(Date(), nullable=True)
    plazo_conservacion_declarado: Mapped[date | None] = mapped_column(Date(), nullable=True)
    cv_archivo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("archivo.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        Enum("en_proceso", "rechazado", "contratado", name="estado_postulante", native_enum=False),
        default="en_proceso",
    )
