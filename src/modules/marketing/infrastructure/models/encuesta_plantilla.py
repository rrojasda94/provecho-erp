"""Plantilla de encuesta: el guion de preguntas que se le manda al cliente.

La plantilla existe para que el guion sea **dato y no código**: Marketing
cambia el orden, agrega una pregunta o corta una rama sin desplegar. Una
sola activa por empresa a la vez — la comparación mes contra mes se cae si
la mitad de las respuestas salieron de otro cuestionario.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class EncuestaPlantilla(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "encuesta_plantilla"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Opcional: una plantilla puede ser del grupo de marcas o de una sola.
    marca_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marca.id"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(120))
    # Encabezado del primer mensaje ("¿Cómo te fue con tu pedido?").
    saludo: Mapped[str] = mapped_column(String(300))
    despedida: Mapped[str] = mapped_column(String(300), default="¡Gracias por responder!")
    activa: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))

    preguntas: Mapped[list["EncuestaPregunta"]] = relationship(  # noqa: F821
        back_populates="plantilla",
        order_by="EncuestaPregunta.orden",
        cascade="all, delete-orphan",
    )
