"""Pregunta de una encuesta: un nodo del guion, no una fila de formulario.

Cada pregunta declara **a dónde sigue la conversación**, y ahí está la
diferencia con un formulario: `siguiente_codigo` es el camino normal y
`saltos` lo desvía según lo que el cliente contestó. Un 2 de 5 lleva a "¿qué
salió mal?" y un 5 a "¿nos recomendarías?" — preguntar las dos a todos es
como no preguntar ninguna.

El destino se guarda por `codigo` y no por id: así una plantilla se escribe
(y se lee) de corrido, y agregar un nodo en medio no obliga a conocer los
UUID que todavía no existen.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin

TIPOS = ("escala", "opcion", "si_no", "texto")


class EncuestaPregunta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "encuesta_pregunta"
    # Nombre explícito en las dos: la convención del proyecto nombra por la
    # primera columna (`uq_%(table_name)s_%(column_0_name)s`) y las dos
    # empiezan por `plantilla_id`, así que se pisarían.
    __table_args__ = (
        UniqueConstraint("plantilla_id", "codigo", name="uq_encuesta_pregunta_codigo"),
        UniqueConstraint("plantilla_id", "orden", name="uq_encuesta_pregunta_orden"),
    )

    plantilla_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("encuesta_plantilla.id"))
    codigo: Mapped[str] = mapped_column(String(30))
    orden: Mapped[int] = mapped_column(Integer)
    texto: Mapped[str] = mapped_column(String(300))
    tipo: Mapped[str] = mapped_column(
        Enum(*TIPOS, name="tipo_pregunta_encuesta", native_enum=False)
    )
    # [{"valor": "1", "etiqueta": "Muy malo"}, ...] — vacío en `texto`.
    opciones: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Camino normal. NULL = acá termina la encuesta.
    siguiente_codigo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # {"1": "que_fallo", "2": "que_fallo"} — desvíos por respuesta.
    saltos: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # La que alimenta `encuesta_satisfaccion.puntaje`: una sola por plantilla,
    # porque el indicador que se reporta al negocio tiene que ser uno.
    es_puntaje: Mapped[bool] = mapped_column(Boolean, default=False)
    # Una pregunta opcional se puede saltar contestando cualquier cosa; hoy
    # solo aplica al comentario libre.
    obligatoria: Mapped[bool] = mapped_column(Boolean, default=True)

    plantilla: Mapped["EncuestaPlantilla"] = relationship(  # noqa: F821
        back_populates="preguntas"
    )
