"""Categoría: agrupador de artículos y activos, a nivel empresa.

Puede ligarse a un asiento contable configurable por tipo de movimiento.
Libremente editable/eliminable, a diferencia del SKU.
"""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Categoria(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "categoria"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    # Cuenta contable por tipo de movimiento (compra, consumo, merma...).
    asiento_contable_config: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
