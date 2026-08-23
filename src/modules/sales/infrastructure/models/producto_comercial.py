"""Producto comercial: ítem vendible en el PDV. Apunta a una receta.

No es inventariable, pero genera registros de venta para medir margen de
contribución. Los combos se modelan en un slice posterior — no son
dependencia dura de venta_item, que guarda su propio precio_unitario al
momento de la venta.

**Las variantes son productos hijos** (`producto_padre_id`): "Pizza
Peperoni Personal/Mediana/Familiar" son tres filas colgadas de "Pizza
Peperoni", cada una con su receta y su precio completo en la lista —no un
recargo sobre un precio base—. Modelarlo así hace que el precio server-side
(RN-PRC-003), el margen por tamaño, el descuento de insumos y el KDS
funcionen sin una línea nueva: todo eso ya opera sobre `producto_comercial`.
El padre existe solo para agrupar: no tiene receta, no tiene precio y no se
vende (RN-COM-022). Elegir variante es obligatorio en el PDV; los grupos de
extras deciden su obligatoriedad en `producto_opcion_grupo`.

**Los extras son productos comerciales** (`es_extra=True`, ADR-018): un
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

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, false, text
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
    # NULL solo en el padre de un grupo de variantes: lo que se prepara lo
    # define la variante elegida, no el agrupador.
    receta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("receta.id"), nullable=True
    )
    # Variante: cuelga de otro producto comercial. Un solo nivel — una
    # variante no admite variantes (RN-COM-022).
    producto_padre_id: Mapped[uuid.UUID | None] = mapped_column(
        # Indexado: la ficha y la carta piden las variantes de un padre en
        # cada carga.
        ForeignKey("producto_comercial.id"), nullable=True, index=True
    )
    # En qué orden salen las tarjetas en el PDV: Personal, Mediana,
    # Familiar no es orden alfabético ni de creación.
    orden: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
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
    # Identificador del sistema del que vino este producto
    # ("__export__.product_template_1307_c1b92172" en un export de Odoo).
    # Es lo que hace idempotente reimportar la misma planilla: sin él,
    # subirla dos veces crea 429 productos duplicados. ADR-052 ya resuelve
    # esto con la columna `ID` cuando el archivo salió de Provecho; esta es
    # la misma idea para un archivo que salió de otra parte.
    ref_externa: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True
    )
    # Dónde quedó el nodo en el lienzo: `{"x": 120, "y": 40}`.
    # ADR-035 decidió NO persistirlo —"mover un nodo no dice nada del
    # producto"— y era cierto mientras el lienzo recolocaba todo en cada
    # cambio de estructura. Con el modelo de atributos el árbol deja de
    # rearmarse solo, así que la posición sí sobrevive y perderla en cada
    # recarga es trabajo tirado.
    lienzo_pos: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
