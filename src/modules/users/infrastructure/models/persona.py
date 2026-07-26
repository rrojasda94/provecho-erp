"""Persona: fuente única de datos de personas naturales (party model).

`trabajador`, `cliente` (natural) y `usuario` (humano) la referencian por
`persona_id` — los nombres/documento nunca se duplican (RN-GEN-007).

`anonimizado_at`: derecho de cancelación (Ley 29733, RN-PER-007). No hay
DELETE de persona — la fila la referencian trabajador/cliente/usuario y
un borrado físico rompería esas FK o dejaría planillas/comprobantes sin
sustento. Anonimizar sobrescribe los campos identificables y preserva la
fila. Ver `docs/architecture/adr/ADR-011-derechos-arco-anonimizacion.md`.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import (
    SoftDeleteMixin,
    TimestampMixin,
    UuidPkMixin,
    VersionedMixin,
)


class Persona(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin, VersionedMixin):
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
    anonimizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
