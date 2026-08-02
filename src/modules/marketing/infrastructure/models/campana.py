"""Campaña de marketing: brief → aprobada → en_curso → cerrada (RN-MKT-003).

`aprobada_por` es el usuario que la aprobó. El enlace con
`decision_gerencial` (obligatorio solo si el gasto sale del presupuesto
anual o supera el límite, RN-GER-007) queda diferido: ni
`presupuesto_anual` ni `decision_gerencial` existen todavía como tablas
— ver ROADMAP → Deuda técnica → marketing.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Campana(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "campana"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(
        Enum(
            "notoriedad",
            "impulso_venta",
            "lanzamiento",
            "medios",
            "evento",
            name="tipo_campana",
            native_enum=False,
        )
    )
    # Los 4 campos del brief (RN-MKT-003): sin los cuatro no pasa de `brief`.
    objetivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publico_objetivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    presupuesto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    kpi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canal: Mapped[str] = mapped_column(String(50))
    estado: Mapped[str] = mapped_column(
        Enum("brief", "aprobada", "en_curso", "cerrada", name="estado_campana", native_enum=False),
        default="brief",
    )
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    aprobada_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
