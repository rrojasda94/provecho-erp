"""Producto comercial: ítem vendible en el PDV. Apunta a una receta.

No es inventariable, pero genera registros de venta para medir margen de
contribución. Modificadores, variantes, combos y precios (lista_precio)
se modelan en un slice posterior — no son dependencia dura de venta_item,
que guarda su propio precio_unitario al momento de la venta.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class ProductoComercial(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "producto_comercial"

    id_interno: Mapped[str] = mapped_column(String(4), unique=True)
    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"))
    nombre: Mapped[str] = mapped_column(String(150))
    # Agrupador para ruteo KDS (pizzas → horno, bebidas → barra). Reusa la
    # tabla `categoria` (agrupador genérico por empresa).
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categoria.id"), nullable=True
    )
    receta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receta.id"))
    # Al descontinuarse pasa a False/archivado, nunca se elimina.
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    margen_contribucion: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    empaque_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("articulo.id"), nullable=True
    )
    # Array `mesa`|`takeout`|`delivery` — en cuáles se descuenta el
    # empaque (RN-EMP-003).
    modalidades_empaque: Mapped[list | None] = mapped_column(JsonB, nullable=True)
