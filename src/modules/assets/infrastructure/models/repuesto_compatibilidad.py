"""Qué repuestos de `inventory` sirven para un activo dado.

Solo un catálogo de sugerencias para la pantalla de alta de una orden de
mantenimiento — no bloquea nada: un repuesto no listado igual se puede
registrar en la orden.
"""

import uuid

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class RepuestoCompatibilidad(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "repuesto_compatibilidad"

    __table_args__ = (
        UniqueConstraint("activo_id", "articulo_id", name="uq_repuesto_compatibilidad"),
    )

    activo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activo.id"))
    # Sin FK: `articulo` es dominio de `inventory`.
    articulo_id: Mapped[uuid.UUID] = mapped_column()
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
