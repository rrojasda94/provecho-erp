"""Producto comercial: ítem vendible en el PDV. Apunta a una receta.

No es inventariable, pero genera registros de venta para medir margen de
contribución. Variantes y combos se modelan en un slice posterior — no son
dependencia dura de venta_item, que guarda su propio precio_unitario al
momento de la venta.

**Los extras son productos comerciales** (`es_extra=True`, ADR-016): un
"extra queso" tiene su propia receta, que se ejecuta en la sucursal y se
suma a la del producto al que se agrega. Modelarlo así, y no como una
entidad aparte, hace que el extra herede sin escribir una línea: precio
server-side por lista (RN-PRC-003), aparición en la carta, y descuento de
insumos por el mismo evento `sales.venta_confirmada`. Lo único propio es a
qué productos se puede agregar (`producto_comercial_extra`) y de qué línea
cuelga al venderse (`venta_item.padre_venta_item_id`).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, false
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
    # Un extra no se vende solo: no sale en la grilla del catálogo, solo
    # dentro del producto que lo admite (RN-COM-021).
    es_extra: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    margen_contribucion: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    empaque_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("articulo.id"), nullable=True
    )
    # Array `mesa`|`takeout`|`delivery` — en cuáles se descuenta el
    # empaque (RN-EMP-003).
    modalidades_empaque: Mapped[list | None] = mapped_column(JsonB, nullable=True)
