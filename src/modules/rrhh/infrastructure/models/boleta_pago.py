"""Boleta de pago: refleja la planilla electrónica (PLAME, RN-RRHH-001).
Operación de dinero → `idempotency_key` (CLAUDE.md: idempotencia en pagos)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class BoletaPago(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "boleta_pago"

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    periodo: Mapped[str] = mapped_column(String(7))  # "YYYY-MM"
    dias_laborados: Mapped[int] = mapped_column()
    remuneracion: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # básico, asignación familiar, HHEE, bonos.
    ingresos: Mapped[dict] = mapped_column(JsonB)
    # ONP/AFP, renta 5ta, adelantos, faltas.
    descuentos: Mapped[dict] = mapped_column(JsonB)
    aportes_empleador: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    neto_pagar: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha_pago: Mapped[date] = mapped_column(Date())
    constancia_firmada: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
