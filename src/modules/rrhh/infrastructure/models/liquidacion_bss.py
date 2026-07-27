"""Liquidación de beneficios sociales: se paga dentro de 48 h del cese
(RN-RRHH-003). Operación de dinero → `idempotency_key`."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class LiquidacionBss(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "liquidacion_bss"

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    fecha_cese: Mapped[date] = mapped_column(Date())
    cts_pendiente: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    vacaciones_truncas: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    gratificacion_trunca: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    otros_adeudos: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha_pago: Mapped[date] = mapped_column(Date())
    dentro_de_plazo: Mapped[bool] = mapped_column(Boolean, default=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
