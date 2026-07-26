"""Contrato laboral: modalidad de contrato de un `trabajador` (marco legal
en docs/rrhh/marco-legal-laboral.md §2). Estado propio (borrador → firmado
→ finalizado) para el flujo de firma (RN-RRHH-012, RN-CTR-004).

Entidad transversal `contrato` genérica (docs/architecture/data-model.md,
convenciones) aún no existe en código — se modela aquí directo en `rrhh`,
mismo diferimiento que `purchases` hizo con `cotizacion` (deuda técnica).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ContratoLaboral(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "contrato_laboral"

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    modalidad: Mapped[str] = mapped_column(
        Enum(
            "indeterminado",
            "modal_inicio_incremento",
            "modal_necesidad_mercado",
            "modal_temporada",
            "tiempo_parcial",
            "jornada_reducida",
            name="modalidad_contrato_laboral",
            native_enum=False,
        )
    )
    jornada_horas_semana: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    remuneracion: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha_inicio: Mapped[date] = mapped_column(Date())
    # Obligatoria si modalidad != indeterminado (RN-CTR-001, validado en dominio).
    fecha_fin: Mapped[date | None] = mapped_column(Date(), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "borrador", "firmado", "finalizado",
            name="estado_contrato_laboral", native_enum=False,
        ),
        default="borrador",
    )
    fecha_firma: Mapped[date | None] = mapped_column(Date(), nullable=True)
