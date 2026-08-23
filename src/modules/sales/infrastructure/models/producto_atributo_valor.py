"""El valor de un atributo **en un producto concreto** — la pieza central.

`product.template.attribute.value` de Odoo. Es a lo que apuntan las dos cosas
que importan:

- la **variante generada**, vía `producto_variante_valor`;
- la **línea de receta condicionada**, vía `receta_item.aplica_valores`.

Que apunten acá y no a `atributo_valor` no es indirección de más: "Familiar"
como idea es una sola, pero "Familiar en la Pizza Peperoni" tiene un
sobreprecio propio y puede estar retirado en un producto y vigente en otro.
Apuntar al valor global obligaría a guardar el precio extra en una tabla
puente igual a ésta con otro nombre.

`precio_extra` **se suma** al precio que resuelve la lista vigente
(RN-PRC-003); no lo reemplaza. La lista sigue mandando sobre el precio base
por sucursal, canal y modalidad.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ProductoAtributoValor(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "producto_atributo_valor"
    __table_args__ = (
        UniqueConstraint(
            "linea_id", "atributo_valor_id", name="uq_producto_atributo_valor"
        ),
    )

    linea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_atributo_linea.id"), index=True
    )
    atributo_valor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atributo_valor.id")
    )
    precio_extra: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal(0), server_default=text("0"), nullable=False
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
