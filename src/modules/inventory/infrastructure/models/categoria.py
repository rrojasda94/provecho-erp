"""Categoría: agrupador de artículos y activos, a nivel empresa.

Puede ligarse a un asiento contable configurable por tipo de movimiento.
Libremente editable/eliminable, a diferencia del SKU.

Es además donde se configura cada cuánto se cuenta lo que agrupa
(RN-INV-007): no hay una periodicidad universal de conteo cíclico — el
abarrote se cuenta al mes y el perecible a diario.
"""

import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin
from src.modules.inventory.domain.rules import FRECUENCIAS_CONTEO

FRECUENCIA_CONTEO = Enum(
    *FRECUENCIAS_CONTEO,
    name="frecuencia_conteo",
    native_enum=False,
)


class Categoria(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "categoria"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    # Cuenta contable por tipo de movimiento (compra, consumo, merma...).
    asiento_contable_config: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # Cada cuánto se cuenta esta categoría. NULL = fuera del conteo cíclico
    # (se cuenta solo si alguien abre un conteo general o una auditoría).
    frecuencia_conteo: Mapped[str | None] = mapped_column(
        FRECUENCIA_CONTEO, nullable=True
    )
