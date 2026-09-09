"""Orden de producción: crear (borrador) → registrar consumo (en_proceso)
→ completar (conforme | no_conforme_reprocesado | no_conforme_desechado).

Costeo (RN-PRD-018) se calcula al completar, nunca a mano.
`plan_produccion`/cronograma queda diferido — la orden se crea sin plan
(ad-hoc) en este slice (deuda técnica, ver ROADMAP).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class OrdenProduccion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "orden_produccion"

    __table_args__ = (
        CheckConstraint(
            "estado IN ('borrador', 'en_proceso', 'conforme', "
            "'no_conforme_reprocesado', 'no_conforme_desechado')",
            name="estado_orden_produccion",
        ),
    )

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
    # Los tres siguientes solo se llenan al completar con resultado
    # `conforme`: son lo que el listener de `inventory` necesita para que el
    # lote del producto terminado nazca con vencimiento real (RN-VNC-001) y
    # no como FIFO por defecto. `fecha_vencimiento`/`lote_codigo` viajan
    # también en el payload de `production.orden_completada`.
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    lote_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Trazabilidad fina de fabricación (RN-LOT-002/003): manipulador_id,
    # envasador_id, linea, variables_proceso — la forma la define quien
    # complete la orden, no hay un esquema fijo todavía (QR queda pendiente).
    trazabilidad: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    # Nullable y únicas: sin clave, un reintento de red puede duplicar el
    # consumo o completar la orden dos veces (deuda técnica, ver ROADMAP).
    consumo_idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    cierre_idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
