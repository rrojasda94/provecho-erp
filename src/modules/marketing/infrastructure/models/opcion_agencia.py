"""Una propuesta dentro de la evaluación: una agencia, o hacerlo en casa.

Hacerlo **interna** es una opción más y se puntúa con los mismos criterios.
Sin ella la evaluación no compara nada: elegir entre tres agencias no
responde la pregunta que RN-MKT-006 hace, que es si hace falta una agencia.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class OpcionAgencia(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "opcion_agencia"

    evaluacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluacion_agencia.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("agencia", "interna", name="tipo_opcion_agencia", native_enum=False)
    )
    nombre: Mapped[str] = mapped_column(String(150))
    # `proveedor` es dominio de `purchases`: se guarda el id sin FK para no
    # atar dos módulos por la base (CLAUDE.md — nada de dominio ajeno).
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    costo: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    plazo_dias: Mapped[int] = mapped_column(Integer)
    # {"experiencia": 4, "precio": 3, ...} — 1 a 5 por criterio declarado.
    puntajes: Mapped[dict] = mapped_column(JsonB)
    # Ponderado con los pesos de la evaluación, calculado al guardar: se
    # persiste para que el ranking histórico no cambie si mañana cambia la
    # fórmula.
    puntaje_total: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)

    evaluacion: Mapped["EvaluacionAgencia"] = relationship(  # noqa: F821
        back_populates="opciones", foreign_keys=[evaluacion_id]
    )
