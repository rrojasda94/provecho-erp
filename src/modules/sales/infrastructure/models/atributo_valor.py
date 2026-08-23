"""Valor posible de un atributo: "Familiar", "Peperoni", "Sin cebolla".

Vive aparte del atributo porque se nombra una vez y se usa en muchos
productos — `product.attribute.value` de Odoo. Lo que un producto concreto
declara no es esto sino `producto_atributo_valor`, que es donde cuelga el
precio extra: "Familiar" cuesta distinto en una pizza que en una lasaña, así
que el sobreprecio no puede vivir acá.

`activo=False` retira el valor de la oferta sin borrarlo: las ventas viejas lo
nombran y una comanda reimpresa tiene que seguir diciendo qué se preparó.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class AtributoValor(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "atributo_valor"
    __table_args__ = (
        UniqueConstraint("atributo_id", "nombre", name="uq_atributo_valor_nombre"),
    )

    atributo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atributo.id"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(80))
    orden: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
