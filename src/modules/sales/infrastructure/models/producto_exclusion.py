"""Combinaciones que no existen: `product.template.attribute.exclusion`.

"Masa integral" no se puede pedir en tamaño Personal porque el bollo no se
hace en ese tamaño. Sin esta tabla, el generador materializa la combinación
imposible, aparece en la carta y alguien la vende.

Es **simétrica en el efecto y dirigida en el dato**: se guarda una fila y el
motor la lee en los dos sentidos. Guardar las dos filas sería la misma verdad
escrita dos veces, y la primera en desincronizarse.
"""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ProductoExclusion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "producto_exclusion"
    __table_args__ = (
        UniqueConstraint(
            "producto_atributo_valor_id",
            "excluye_valor_id",
            name="uq_producto_exclusion",
        ),
    )

    producto_atributo_valor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_atributo_valor.id"), index=True
    )
    excluye_valor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_atributo_valor.id")
    )
