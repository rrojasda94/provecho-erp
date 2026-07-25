"""Ítem de venta: producto comercial, cantidad y precio al momento de
vender (snapshot — no depende de lista_precio para existir).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class VentaItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "venta_item"

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"))
    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    descuento: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
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
