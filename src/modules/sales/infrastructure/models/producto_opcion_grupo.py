"""Grupo de extras de un producto, con cuántos hay que elegir.

"Salsas: elige 1" y "Toppings: hasta 3, opcional" son el mismo mecanismo con
distinto mínimo. El mínimo es lo que hace obligatorio al grupo: `minimo >= 1`
bloquea el agregado al carrito hasta que se elija (RN-COM-023). No hay
columna `obligatorio` porque sería el mismo dato dos veces, y dos datos que
dicen lo mismo terminan diciendo cosas distintas.

El grupo de tamaños (Personal/Mediana/Familiar) NO vive acá: son variantes
—productos hijos con receta y precio propios— y elegir una siempre es
obligatorio. Un grupo de este tipo agrupa extras, que son opcionales por
naturaleza salvo que el producto diga lo contrario.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ProductoOpcionGrupo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "producto_opcion_grupo"
    __table_args__ = (
        UniqueConstraint("producto_comercial_id", "nombre", name="uq_producto_grupo"),
    )

    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
    nombre: Mapped[str] = mapped_column(String(50))
    # Cuántas opciones del grupo hay que elegir como mínimo. 0 = opcional.
    minimo: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    # Tope de opciones distintas del grupo en una misma línea. NULL = sin
    # tope. Distinto de `producto_comercial_extra.maximo`, que limita
    # unidades de UN extra (3 porciones de queso).
    maximo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orden: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
