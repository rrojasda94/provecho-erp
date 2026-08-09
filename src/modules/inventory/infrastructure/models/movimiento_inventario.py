"""movimiento_inventario: rastro inmutable de todo cambio de stock.

Solo inserción — el stock es derivable y auditable. `cantidad` con signo
(+ ingreso, − salida).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin

TIPO_MOVIMIENTO = Enum(
    "recepcion_compra",
    "transferencia_salida",
    "transferencia_entrada",
    "consumo_venta",
    "consumo_produccion",
    # Consumo de personal (RN-COM-025): salió del almacén y nadie lo pagó.
    "consumo_interno",
    "produccion_entrada",
    "ajuste",
    "devolucion",
    name="tipo_movimiento",
    native_enum=False,
)

MOTIVO_AJUSTE = Enum(
    "sobrante",
    "faltante",
    "merma",
    "error_registro",
    name="motivo_ajuste",
    native_enum=False,
)


class MovimientoInventario(Base, UuidPkMixin):
    __tablename__ = "movimiento_inventario"

    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    tipo: Mapped[str] = mapped_column(TIPO_MOVIMIENTO)
    # Solo si tipo=ajuste.
    motivo_ajuste: Mapped[str | None] = mapped_column(MOTIVO_AJUSTE, nullable=True)
    # NULL si el artículo no controla lote. Una salida que abarca varios
    # lotes genera un movimiento por lote — la traza queda por lote, no
    # agregada (ADR-015).
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lote.id"), nullable=True
    )
    # Por qué se tomó un lote distinto del que FEFO sugería. Obligatorio al
    # hacer el override y NULL en todo lo demás: saltearse FEFO es una
    # decisión de una persona (un lote dañado, una promoción, un pedido que
    # exige otro vencimiento) y sin el motivo la traza dice qué salió pero no
    # por qué salió eso.
    motivo_lote: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Documento origen (id de compra, venta, ajuste, transferencia...).
    referencia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
