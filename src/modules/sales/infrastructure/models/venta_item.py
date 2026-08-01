"""Ítem de venta: producto comercial, cantidad y precio al momento de
vender (snapshot — no depende de lista_precio para existir).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class VentaItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "venta_item"

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"))
    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
    # Línea de la que cuelga este extra (RN-COM-021). NULL = línea normal.
    # Un extra es una línea propia y no una columna del padre porque tiene
    # su propia receta, su propio precio de lista y su propio avance en
    # cocina; aplanarlo perdería las tres cosas.
    padre_venta_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venta_item.id"), nullable=True, index=True
    )
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    descuento: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    # Cuenta a la que pertenece la línea cuando se divide el pedido entre
    # varios pagadores (RN-COM-018). Todo empieza en 1: una venta sin dividir
    # es una venta con un solo grupo de cobro.
    grupo_cobro: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    # Avance en cocina (KDS). Fuente única del progreso del pedido: todas
    # las pantallas leen/escriben este estado. `updated_at` marca el último
    # cambio (base para tiempos de preparación).
    estado_preparacion: Mapped[str] = mapped_column(
        Enum(
            "pendiente",
            "en_preparacion",
            "listo",
            "entregado",
            name="estado_preparacion_item",
            native_enum=False,
        ),
        default="pendiente",
    )
