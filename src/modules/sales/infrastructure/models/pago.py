"""Pago: una venta puede tener varios (pago dividido, confirmado
2026-07-20 como caso real) — la suma de `monto` debe igualar
`venta.total` antes de `estado=pagada` (RN-COM-016, validado en el
dominio, no en el esquema).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Pago(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "pago"

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"))
    medio_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medio_pago.id"))
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Cuenta que este pago cancela (RN-COM-018). Los pagos de un mismo grupo
    # suman contra el total de ESE grupo, no contra el de la venta entera.
    grupo_cobro: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    # Ej. "izipay" — proveedor de la pasarela, si aplica (nullable: no
    # todo medio de pago pasa por pasarela, ej. efectivo).
    pasarela: Mapped[str | None] = mapped_column(String(50), nullable=True)
    referencia_externa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Obligatoria al registrar pago (RN-COM-002).
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "pendiente",
            "confirmado",
            "rechazado",
            name="estado_pago",
            native_enum=False,
        ),
        default="pendiente",
    )
