"""Empresa: unidad legal (RUC) de un grupo empresarial. Es el tenant raíz."""

import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Empresa(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "empresa"

    grupo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grupo.id"))
    razon_social: Mapped[str] = mapped_column(String(255))
    ruc: Mapped[str] = mapped_column(String(11), unique=True)
    domicilio_fiscal: Mapped[str] = mapped_column(String(255))
    contacto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tipo: Mapped[str] = mapped_column(
        Enum(
            "operativa",
            "logistica",
            "servicios",
            "asesoria",
            "transporte",
            name="tipo_empresa",
            native_enum=False,
        )
    )
    # Determina exoneración de IGV y tasa reducida de IR (RN-IMP-001).
    zona_tributaria: Mapped[str] = mapped_column(
        Enum(
            "amazonia_ley27037",
            "general",
            name="zona_tributaria",
            native_enum=False,
        ),
        default="general",
    )
    config_fiscal: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
