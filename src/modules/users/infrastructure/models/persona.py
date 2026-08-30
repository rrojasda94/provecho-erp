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
    UbicacionMixin,
    UuidPkMixin,
    VersionedMixin,
)
from src.shared.documento import TIPOS


class Persona(
    Base,
    UuidPkMixin,
    TimestampMixin,
    SoftDeleteMixin,
    VersionedMixin,
    UbicacionMixin,
):
    __tablename__ = "persona"

    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    # Documento OPCIONAL desde 2026-07-28 (ADR-018): un cliente de mostrador
    # o delivery no siempre quiere darlo, y el teléfono alcanza para
    # identificarlo y volverle a vender. Se completa después sin problema.
    # Trabajador y usuario SÍ lo exigen — esa validación vive en sus casos
    # de uso (`users.application.admin`), no en el esquema, porque `persona`
    # es compartida y no todos sus roles tienen la misma exigencia.
    # El UNIQUE se conserva: un índice único admite varios NULL.
    tipo_documento: Mapped[str | None] = mapped_column(
        # `create_constraint=True` a propósito: sin él SQLAlchemy no emite
        # ningún CHECK (default desde 1.4), el valor fuera del vocabulario
        # entra sin ruido y revienta 500 en **cada lectura** posterior de
        # esa fila. Ver migración `c9f4a2e70b18`.
        Enum(*TIPOS, name="tipo_documento", native_enum=False, create_constraint=True),
        nullable=True,
    )
    numero_documento: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
    )
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    domicilio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    anonimizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
