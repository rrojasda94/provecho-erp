"""Pieza de contenido del calendario: solo se publica si es pertinente a la
marca (RN-MKT-002) y su uso de marca está validado (RN-MKT-001)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class PiezaContenido(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "pieza_contenido"

    # Opcional: hay contenido de marca que no cuelga de ninguna campaña.
    campana_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campana.id"), nullable=True
    )
    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"))
    titulo: Mapped[str] = mapped_column(String(150))
    canal: Mapped[str] = mapped_column(String(50))
    fecha_publicacion: Mapped[date] = mapped_column(Date)
    pertinente_marca: Mapped[bool] = mapped_column(Boolean, default=False)
    uso_marca_validado: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str] = mapped_column(
        Enum(
            "planificada",
            "publicada",
            "descartada",
            name="estado_pieza_contenido",
            native_enum=False,
        ),
        default="planificada",
    )
    # Alcance/interacción por canal: cada red reporta métricas distintas.
    metricas: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
