"""Carga de combustible de un vehículo. El comprobante se registra primero en
`purchases` (compra directa con un artículo `tipo="servicio"`, ADR-082); acá
solo se liga ese comprobante al vehículo con el kilometraje y los galones
(decisión con el usuario, 2026-09-09) — es lo que permite comparar consumo
contra kilometraje y detectar un problema.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class CargaCombustible(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "carga_combustible"

    vehiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehiculo.activo_id"))
    fecha: Mapped[date] = mapped_column(Date)
    galones: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tipo_combustible: Mapped[str | None] = mapped_column(String(20), nullable=True)
    km_odometro: Mapped[int] = mapped_column()
    # NOT NULL + UNIQUE: toda carga sustenta su propio comprobante recibido
    # (RN-VEH-006) y ninguno se reutiliza en dos cargas.
    comprobante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comprobante.id"), unique=True)
    # Derivados y congelados al registrar (mismo criterio que
    # `alerta_pedido.minutos_umbral`): recalcularlos después de que cambie el
    # historial reescribiría una carga que en su momento fue normal.
    km_recorridos: Mapped[int | None] = mapped_column(nullable=True)
    rendimiento_km_gal: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    anomalo: Mapped[bool] = mapped_column(Boolean, default=False)
    registrado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
