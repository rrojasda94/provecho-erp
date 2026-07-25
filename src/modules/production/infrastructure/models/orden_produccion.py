"""Orden de producción: crear (borrador) → registrar consumo (en_proceso)
→ completar (conforme | no_conforme_reprocesado | no_conforme_desechado).

Costeo (RN-PRD-018) se calcula al completar, nunca a mano.
`plan_produccion`/cronograma queda diferido — la orden se crea sin plan
(ad-hoc) en este slice (deuda técnica, ver ROADMAP).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class OrdenProduccion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "orden_produccion"

    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    cantidad_planeada: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    cantidad_producida: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "borrador",
            "en_proceso",
            "conforme",
            "no_conforme_reprocesado",
            "no_conforme_desechado",
            name="estado_orden_produccion",
            native_enum=False,
        ),
        default="borrador",
    )
    horas_hombre: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    costo_insumos: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    costo_mano_obra: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    costo_real_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    # Solo si estado=no_conforme_desechado (RN-PRD-015/018).
    merma_cantidad: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    merma_motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidencia_destruccion_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
