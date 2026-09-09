"""Orden de compra: proveedor → OC (borrador → emitida → recepción).

Tipo `activo` (ADR-099, 2026-09-09) compra un `requerimiento_activo` en vez
de artículos de `inventory`: sin `almacen_destino_id` (no hay almacén de
destino — el activo no entra a stock) y con `requerimiento_activo_id`
obligatorio. La aprobación y la emisión son las mismas de cualquier OC —
`emitir_orden_compra` no distingue tipo—; lo que queda fuera de este slice
es la doble aprobación de área/gerencia y las cotizaciones mínimas que el
proceso completo (PROC-CTB-010) describe, deuda técnica declarada.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class OrdenCompra(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "orden_compra"

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('insumo', 'activo')",
            name="tipo_orden_compra",
        ),
        CheckConstraint(
            "origen IN ('oc', 'directa')",
            name="origen_orden_compra",
        ),
        CheckConstraint(
            "estado IN ('borrador', 'emitida', 'recibida_parcial', "
            "'recibida', 'anulada')",
            name="estado_orden_compra",
        ),
        # Uno exige al otro (RN-CMP nueva): una OC de activo sin su
        # requerimiento no tendría qué recibir, y una de insumo con uno
        # apuntaría a un dato que nadie lee.
        CheckConstraint(
            "(tipo = 'activo') = (requerimiento_activo_id IS NOT NULL)",
            name="requerimiento_activo_si_tipo_activo",
        ),
    )

    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proveedor.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("insumo", "activo", name="tipo_orden_compra", native_enum=False)
    )
    # `directa` = compra a proveedor sustentada solo con el comprobante
    # recibido, sin pasar por emisión/recepción — nace ya `recibida`.
    origen: Mapped[str] = mapped_column(
        Enum("oc", "directa", name="origen_orden_compra", native_enum=False),
        default="oc",
    )
    # Origen opcional — entidad `cotizacion` aún sin modelar (deuda técnica).
    cotizacion_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Obligatorio si tipo=activo.
    requerimiento_activo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requerimiento_activo.id"), nullable=True
    )
    # Nulo si tipo=activo: un activo no entra a un almacén de inventory.
    almacen_destino_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("almacen.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        Enum(
            "borrador",
            "emitida",
            "recibida_parcial",
            "recibida",
            "anulada",
            name="estado_orden_compra",
            native_enum=False,
        ),
        default="borrador",
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    emitido_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    fecha_emision: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
