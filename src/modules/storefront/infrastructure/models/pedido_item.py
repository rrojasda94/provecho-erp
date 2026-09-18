"""Línea de un pedido del sitio de marca. `nombre_congelado`/
`precio_unitario_congelado` son una foto del momento del checkout — el
precio real y autoritativo lo vuelve a fijar `sales` al confirmar
(RN-PRC-003); esto es solo lo que se le muestra al cliente en `/pedido/{id}`
sin tener que volver a consultar la carta pública.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class StorefrontPedidoItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "storefront_pedido_item"

    pedido_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("storefront_pedido.id"), index=True
    )
    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
    nombre_congelado: Mapped[str] = mapped_column(String(150))
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario_congelado: Mapped[Decimal] = mapped_column(Numeric(10, 2))
