"""Venta: alcance corregido 2026-07-14 (RN-COM-005) — termina en el envío
del pedido a cocina y el cobro. Preparación/entrega pertenecen al futuro
proceso "cumplimiento de pedido", aún sin definir.

Toda venta confirmada ya ES una Orden de Pedido (glosario), tenga o no
`cotizacion_id` — `numero_orden` es el correlativo legible por sucursal y
día que ve el personal (cocina/mostrador/KDS); `idempotency_key` es
técnico (anti-duplicado), no se muestra a nadie. La generación del
correlativo (siguiente número del día para esa sucursal) es lógica de
aplicación, aún no construida — el esquema solo declara la unicidad.

Medio de pago, pago, comprobante y demás entidades de PROC-COM-002 (Cobro)
se modelan en un slice posterior de este mismo proceso Venta.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Venta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "venta"
    __table_args__ = (UniqueConstraint("sucursal_id", "fecha_orden", "numero_orden"),)

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    # Día de negocio de la orden (lo fija la aplicación al crear) — base
    # estable para el correlativo, independiente de la hora exacta de
    # created_at.
    fecha_orden: Mapped[date] = mapped_column(default=date.today)
    numero_orden: Mapped[int] = mapped_column(Integer)
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
    # Contador de impresiones de comanda (>1 = reimpresión, auditable).
    comanda_impresa_veces: Mapped[int] = mapped_column(Integer, default=0)
    # Para quién es el pedido, como lo canta el mesero: "Mesa 5", "Carlos",
    # "Rappi #1042". Texto libre — no exige cliente registrado. Visible en
    # KDS y comanda para aclarar problemas en cocina.
    referencia_atencion: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
