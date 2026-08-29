"""Orden de compra: proveedor → OC (borrador → emitida → recepción). Tipo
`activo` declarado en el esquema pero rechazado en la capa de aplicación
de este slice (requiere `requerimiento_activo` con doble aprobación,
deuda técnica — ver ROADMAP).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class OrdenCompra(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "orden_compra"

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
    # Obligatorio si tipo=activo — entidad `requerimiento_activo` diferida.
    requerimiento_activo_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    almacen_destino_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
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
