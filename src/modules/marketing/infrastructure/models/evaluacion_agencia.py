"""Evaluación agencia vs. interna de una campaña (RN-MKT-006).

Marketing evalúa, Gerencia valida. La tabla existe para que esa validación
tenga contra qué comparar: sin criterios ponderados escritos **antes** de
ver las propuestas, "elegimos la mejor" no se puede auditar seis meses
después, que es justo cuando alguien pregunta por qué se pagó lo que se pagó.

La agencia es un **servicio**: se formaliza por contrato y la paga
Contabilidad, no pasa por `purchases` (que compra el material, RN-MKT-004).
`contrato` todavía no existe como tabla — ver ROADMAP → Deuda técnica.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class EvaluacionAgencia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "evaluacion_agencia"

    campana_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campana.id"))
    objetivo: Mapped[str] = mapped_column(String(255))
    presupuesto_referencia: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # [{"codigo": "experiencia", "etiqueta": "...", "peso": 30}, ...].
    # Se congelan al crear la evaluación: cambiar el peso después de ver las
    # propuestas es elegir primero y justificar después.
    criterios: Mapped[list] = mapped_column(JsonB)
    estado: Mapped[str] = mapped_column(
        Enum(
            "borrador",
            "evaluada",
            "decidida",
            name="estado_evaluacion_agencia",
            native_enum=False,
        ),
        default="borrador",
    )
    opcion_elegida_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opcion_agencia.id", use_alter=True), nullable=True
    )
    decidida_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    fecha_decision: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Obligatorio cuando la elegida no es la mejor puntuada o se sale del
    # presupuesto: la excepción se puede tomar, pero queda escrita.
    motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))

    opciones: Mapped[list["OpcionAgencia"]] = relationship(  # noqa: F821
        back_populates="evaluacion",
        cascade="all, delete-orphan",
        foreign_keys="OpcionAgencia.evaluacion_id",
    )
