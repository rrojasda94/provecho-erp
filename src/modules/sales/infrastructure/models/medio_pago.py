"""Medio de pago: catálogo por empresa (decisión 2026-07-20 — cada
empresa del grupo pacta su propia pasarela/comisión, no es global).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class MedioPago(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "medio_pago"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    nombre: Mapped[str] = mapped_column(String(50))
    direccion: Mapped[str] = mapped_column(
        Enum("cobro", "pago", "ambos", name="direccion_medio_pago", native_enum=False)
    )
    tipo: Mapped[str] = mapped_column(
        Enum(
            "efectivo",
            "tarjeta_credito",
            "tarjeta_debito",
            "billetera_digital",
            "transferencia",
            "cheque",
            "credito_empresarial",
            name="tipo_medio_pago",
            native_enum=False,
        )
    )
    comision_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(0))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    activa_promocion: Mapped[bool] = mapped_column(Boolean, default=False)
    # Si a crédito aplica otra lista de precios (RN-MDP-001) — lista_precio
    # se modela en un slice posterior, sin FK todavía.
    lista_precio_credito_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
