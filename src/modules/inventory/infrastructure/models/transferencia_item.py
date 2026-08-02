"""transferencia_item: una línea despachada, por SKU **y lote**.

Es por lote y no por SKU porque el despacho reparte por FEFO: sacar 10 kg
puede tomar tres lotes distintos, y el destino tiene que recibir esos
mismos tres (ADR-015). Una fila por movimiento de salida generado.

`cantidad_recibida` NULL mientras está en tránsito. Al recibir, una
diferencia contra `cantidad_enviada` no se corrige sola: queda registrada
y es auditable (RN-INV-002).
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class TransferenciaItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "transferencia_item"

    transferencia_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transferencia.id")
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    # NULL si el artículo no controla lote.
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lote.id"), nullable=True
    )
    cantidad_enviada: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    cantidad_recibida: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )

    @property
    def diferencia(self) -> Decimal | None:
        if self.cantidad_recibida is None:
            return None
        return self.cantidad_recibida - self.cantidad_enviada
