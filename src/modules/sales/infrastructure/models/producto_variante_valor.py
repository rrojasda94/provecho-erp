"""Qué combinación **es** una variante ya materializada.

La variante sigue siendo una fila de `producto_comercial` con
`producto_padre_id` (ADR-023), y eso no es una concesión: es lo que hace que
el precio server-side, el margen por tamaño, el ruteo del KDS, el precio
congelado de `venta_item` y la réplica al hub sigan funcionando sin escribir
una línea. Lo que cambia con ADR-055 es **quién** crea esa fila —el generador,
no una persona— y qué lleva colgado: los valores que la identifican.

Sin esta tabla, "Pizza Peperoni Familiar" sería un nombre y nada más; con
ella, el motor sabe que esa fila *es* {Tamaño: Familiar, Sabor: Peperoni} y
puede decidir qué líneas de receta le tocan.
"""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ProductoVarianteValor(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "producto_variante_valor"
    __table_args__ = (
        UniqueConstraint(
            "producto_comercial_id",
            "producto_atributo_valor_id",
            name="uq_producto_variante_valor",
        ),
    )

    # La fila **hija**: la que se vende y se prepara.
    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id"), index=True
    )
    producto_atributo_valor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_atributo_valor.id"), index=True
    )
