"""Qué atributo ofrece un producto: `product.template.attribute.line`.

"Pizza Peperoni ofrece Tamaño" es esta fila. Qué valores de Tamaño ofrece
—todos o algunos— lo dice `producto_atributo_valor`, que cuelga de acá.

Existe como tabla propia y no como columna en el valor porque la elección es
en dos pasos y los dos son del negocio: primero *qué dimensión* tiene este
plato, después *qué opciones* de esa dimensión. Sin la línea, quitarle el
Tamaño a un producto sería borrar sus valores uno por uno y quedarse sin
saber que alguna vez lo tuvo.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ProductoAtributoLinea(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "producto_atributo_linea"
    __table_args__ = (
        UniqueConstraint(
            "producto_comercial_id", "atributo_id", name="uq_producto_atributo_linea"
        ),
    )

    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id"), index=True
    )
    atributo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atributo.id"))
    # El orden en que el PDV pregunta. RN-PRD-004 fija el orden de aplicación
    # de los modificadores; esto fija el de la pantalla, que no es lo mismo.
    orden: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
