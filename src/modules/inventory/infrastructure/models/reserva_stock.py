"""reserva_stock: compromiso sobre stock que todavía está físicamente en
el almacén (RN-INV-009..012).

Stock disponible = stock físico − Σ reservas activas. La reserva no mueve
`stock`: lo que ya salió es un `movimiento_inventario`, no una reserva.
Sirve para que dos sucursales no se prometan el mismo saco de harina.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

TIPO_RESERVA = Enum(
    "solicitud",
    "produccion",
    "merma",
    "carrito",
    name="tipo_reserva",
    native_enum=False,
)

# Solo si tipo=merma: qué la originó (RN-INV-012).
MOTIVO_RESERVA_MERMA = Enum(
    "devolucion",
    "rechazo_sucursal",
    "auditoria",
    name="motivo_reserva_merma",
    native_enum=False,
)

ESTADO_RESERVA = Enum(
    "activa",
    "liberada",
    "consumida",
    "pendiente_desecho",
    name="estado_reserva",
    native_enum=False,
)


class ReservaStock(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "reserva_stock"

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    tipo: Mapped[str] = mapped_column(TIPO_RESERVA)
    # Documento que la originó (solicitud_id / orden_produccion_id /
    # carrito_id). Sin FK: apunta a tablas distintas según `tipo`.
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    motivo: Mapped[str | None] = mapped_column(MOTIVO_RESERVA_MERMA, nullable=True)
    estado: Mapped[str] = mapped_column(ESTADO_RESERVA, default="activa")
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Quién la soltó a mano ante desabastecimiento (RN-INV-011).
    liberado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
