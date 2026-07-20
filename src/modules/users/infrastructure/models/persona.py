"""Persona: fuente única de datos de personas naturales (party model).

`trabajador`, `cliente` (natural) y `usuario` (humano) la referencian por
`persona_id` — los nombres/documento nunca se duplican (RN-GEN-007).
"""

from datetime import date

from sqlalchemy import Date, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Persona(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "persona"

    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    tipo_documento: Mapped[str] = mapped_column(
        Enum("dni", "ce", "pasaporte", name="tipo_documento", native_enum=False)
    )
    numero_documento: Mapped[str] = mapped_column(String(20), unique=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    domicilio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
