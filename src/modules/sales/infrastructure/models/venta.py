"""Venta: alcance corregido 2026-07-14 (RN-COM-005) — termina en el envío
del pedido a cocina y el cobro. Preparación/entrega pertenecen al futuro
proceso "cumplimiento de pedido", aún sin definir.

Medio de pago, pago, comprobante y demás entidades de PROC-COM-002 (Cobro)
se modelan en un slice posterior de este mismo proceso Venta.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Venta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "venta"

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    punto_venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("punto_venta.id"))
    canal: Mapped[str] = mapped_column(
        Enum("pdv", "agente_ia", "delivery", name="canal_venta", native_enum=False)
    )
    modalidad: Mapped[str] = mapped_column(
        Enum("mesa", "takeout", "delivery", name="modalidad_venta", native_enum=False)
    )
    # Opcional — venta de servicio o del área comercial originada en
    # cotización aceptada por el cliente (RN-COM-004). Entidad `cotizacion`
    # se modela en el slice de Compras/Comercial que la comparte.
    cotizacion_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cliente.id"), nullable=True
    )
    # Cajero o agente_ia — quien atendió; base del ranking de venta por
    # trabajador (join usuario_id -> trabajador.usuario_id).
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    estado: Mapped[str] = mapped_column(
        Enum("orden", "pagada", "facturada", "anulada", name="estado_venta", native_enum=False),
        default="orden",
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    # `rappi` | `ubereats` | `pedidosya` | ... si un rider de plataforma
    # externa hizo el delivery (RN-PER-003).
    repartidor_externo_plataforma: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
