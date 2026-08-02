"""Postulante: candidato en proceso de selección. Es la ficha del expediente
de la búsqueda y avanza por el tablero de contratación (`estado`) desde que
llega la postulación hasta que pasa el periodo de prueba.

Sus datos NO viven en `persona`: el pool de candidatos es gente ajena a la
empresa y la mayoría nunca entra. `persona` (y con ella `trabajador`) se crea
recién al contratar. Datos sujetos a consentimiento previo (RN-PER-004,
Ley 29733).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin
from src.modules.rrhh.domain.rules import ESTADOS_POSTULANTE


class Postulante(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "postulante"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Nulo si es postulación espontánea o referido fuera de una búsqueda
    # abierta (banco de candidatos).
    convocatoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("convocatoria.id"), nullable=True
    )
    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    puesto_postulado: Mapped[str] = mapped_column(String(150))
    fecha_postulacion: Mapped[date] = mapped_column(Date())
    # Para medir qué canal trae a los que sí se contratan.
    canal_origen: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Respuestas crudas del formulario: cada convocatoria pregunta lo suyo,
    # no hay esquema fijo que valga la pena mantener.
    respuestas: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # RN-PER-004: consentimiento previo, informado y expreso.
    consentimiento_datos: Mapped[bool] = mapped_column(Boolean, default=False)
    consentimiento_fecha: Mapped[date | None] = mapped_column(Date(), nullable=True)
    plazo_conservacion_declarado: Mapped[date | None] = mapped_column(Date(), nullable=True)
    cv_archivo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("archivo.id"), nullable=True
    )
    # Se llenan al contratar: recién ahí el candidato entra a `persona`.
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("persona.id"), nullable=True
    )
    trabajador_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trabajador.id"), nullable=True
    )
    # Por qué se descartó: sin esto no hay cómo defender la decisión ante un
    # reclamo de discriminación (Ley 26772). **Sobrevive a la anonimización**,
    # así que se escribe el criterio, nunca datos personales.
    motivo_descarte: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Derecho de cancelación (Ley 29733, RN-PER-007): la ficha se conserva
    # sin datos identificables, no se borra. Ver `application/privacidad.py`.
    anonimizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS_POSTULANTE, name="estado_postulante", native_enum=False),
        default="recibido",
    )
