"""Convocatoria: la búsqueda de personal desde la requisición aprobada hasta
su cierre. Es el expediente al que cuelgan los postulantes (RN-RRHH-013: sin
perfil de puesto aprobado no se publica)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Convocatoria(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "convocatoria"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Dónde se necesita cubrir el puesto; nulo si es transversal a la empresa.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    puesto: Mapped[str] = mapped_column(String(150))
    # Slug del perfil aprobado en `docs/rrhh/perfiles/`. Sin él no hay
    # publicación (RN-RRHH-013) — el ERP guarda la referencia, no el perfil.
    perfil_puesto: Mapped[str | None] = mapped_column(String(100), nullable=True)
    motivo: Mapped[str] = mapped_column(
        Enum(
            "reemplazo",
            "refuerzo",
            "puesto_nuevo",
            name="motivo_convocatoria",
            native_enum=False,
        )
    )
    vacantes: Mapped[int] = mapped_column(Integer, default=1)
    jornada_horas_semana: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True
    )
    # Rango salarial aprobado en la requisición: la oferta no sale de acá.
    remuneracion_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    remuneracion_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fecha_objetivo: Mapped[date | None] = mapped_column(Date(), nullable=True)
    fecha_limite: Mapped[date | None] = mapped_column(Date(), nullable=True)
    fecha_publicacion: Mapped[date | None] = mapped_column(Date(), nullable=True)
    # Se genera al publicar: identifica la convocatoria en el formulario
    # público. Un borrador no tiene token, así que no recibe postulaciones.
    token_publico: Mapped[str | None] = mapped_column(
        String(43), nullable=True, unique=True, index=True
    )
    estado: Mapped[str] = mapped_column(
        Enum(
            "borrador",
            "publicada",
            "cerrada",
            name="estado_convocatoria",
            native_enum=False,
        ),
        default="borrador",
    )
