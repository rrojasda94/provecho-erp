"""solicitud_item: un SKU dentro de una solicitud de insumos.

Tres cantidades porque son tres momentos distintos y las diferencias entre
ellas son justo lo auditable: lo que el local pidió, lo que el supervisor
aprobó (RN-INV-001: nunca se despacha más que esto) y lo que el central
llegó a despachar cuando el stock no alcanzó.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class SolicitudItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "solicitud_item"
    __table_args__ = (UniqueConstraint("solicitud_id", "sku_id"),)

    solicitud_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("solicitud_insumos.id")
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sku.id"))
    cantidad_solicitada: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    cantidad_aprobada: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    cantidad_despachada: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
