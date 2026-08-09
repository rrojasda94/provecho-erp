"""Respuesta a un nodo concreto de la encuesta.

`encuesta_satisfaccion.puntaje`/`comentario` siguen existiendo como el
resumen que consume el negocio; acá queda el detalle nodo por nodo, que es
lo único que permite reconstruir por qué la conversación tomó una rama y no
la otra. Uno por pregunta: reenviar la misma respuesta no duplica la fila.
"""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class EncuestaRespuesta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "encuesta_respuesta"
    __table_args__ = (UniqueConstraint("encuesta_id", "pregunta_id"),)

    encuesta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("encuesta_satisfaccion.id"))
    pregunta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("encuesta_pregunta.id"))
    valor: Mapped[str] = mapped_column(String(500))
