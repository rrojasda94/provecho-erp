"""conteo_item: un SKU dentro de un conteo.

`cantidad_sistema` se congela al abrir el conteo, no al cerrarlo: entre
ambos momentos el almacén sigue operando, y comparar lo contado contra un
stock que se movió mientras se contaba produce diferencias que no existen.

`diferencia` no se guarda — es `cantidad_contada − cantidad_sistema` y un
campo derivado almacenado solo puede desincronizarse.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ConteoItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "conteo_item"
    __table_args__ = (UniqueConstraint("conteo_id", "sku_id"),)

    conteo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conteo.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    cantidad_sistema: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal(0)
    )
    # NULL mientras nadie lo haya contado: un ítem no contado no genera
    # ajuste al cerrar (si no, un conteo parcial inventaría faltantes).
    cantidad_contada: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )

    @property
    def diferencia(self) -> Decimal | None:
        if self.cantidad_contada is None:
            return None
        return self.cantidad_contada - self.cantidad_sistema
