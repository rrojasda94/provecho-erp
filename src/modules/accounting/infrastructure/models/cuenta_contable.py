"""Cuenta contable: plan de cuentas por empresa (data-model §8)."""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class CuentaContable(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cuenta_contable"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(150))
    tipo: Mapped[str] = mapped_column(
        Enum(
            "activo", "pasivo", "patrimonio", "ingreso", "gasto",
            name="tipo_cuenta_contable", native_enum=False,
        )
    )
    # Árbol simple del plan de cuentas; sin límite de niveles.
    cuenta_padre_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuenta_contable.id"), nullable=True
    )
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
