"""Atributo de producto: la dimensión por la que un producto se combina.

"Tamaño", "Sabor", "Mitad 1", "Temperatura". Es el equivalente de
`product.attribute` de Odoo, y existe por una razón concreta: hasta ahora
cada combinación vendible era **una fila de producto** con su propia receta
(ADR-023). Una pizza mitad-y-mitad con 19 sabores por mitad son 361
combinaciones — 361 productos y 361 recetas que alguien tendría que teclear.
Con atributos son dos filas acá y una receta con líneas condicionadas.

`modo_variante` decide si la combinación se **materializa** como fila hija de
`producto_comercial` (ADR-055):

- `siempre`   — se generan todas las combinaciones al vincular el atributo.
                Hace falta cuando cada combinación tiene precio o receta
                propios: una Familiar no cuesta lo mismo que una Personal.
- `dinamica`  — la fila se crea la primera vez que esa combinación se vende.
                Para atributos anchos donde solo unas pocas se piden.
- `nunca`     — no se genera fila ninguna. El valor elegido viaja en la línea
                de venta y solo sirve para filtrar líneas de receta. Es lo
                correcto para "sin cebolla" o "bien caliente": no cambian el
                precio ni el producto, cambian lo que se consume.

`display` es cómo lo dibuja el PDV. No cambia ninguna aritmética —igual que
`producto_opcion_grupo` no tiene `tipo` (ADR-035 §5)—, pero un atributo de 19
valores en botones de radio es una pantalla inusable y en desplegable no.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Atributo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "atributo"
    __table_args__ = (
        UniqueConstraint("empresa_id", "nombre", name="uq_atributo_empresa_nombre"),
        UniqueConstraint("ref_externa", name="uq_atributo_ref_externa"),
    )

    # De la empresa y no de la marca: dos marcas del mismo grupo comparten
    # "Tamaño", y duplicarlo por marca haría que un reporte del grupo tuviera
    # dos filas para el mismo hecho.
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    modo_variante: Mapped[str] = mapped_column(
        String(10), default="nunca", server_default=text("'nunca'"), nullable=False
    )
    display: Mapped[str] = mapped_column(
        String(10), default="radio", server_default=text("'radio'"), nullable=False
    )
    orden: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    # Identificador del sistema de origen ("__export__.product_attribute_9_...").
    # Es lo que hace que reimportar la misma planilla actualice en vez de
    # duplicar, sin pedirle a nadie que copie un UUID a mano. ADR-052 usa `ID`
    # para lo mismo dentro de Provecho; esto es la clave del **otro** sistema.
    ref_externa: Mapped[str | None] = mapped_column(String(120), nullable=True)
