"""Movimiento de dinero: registro genérico de tesorería (data-model §8/§5).
Hoy solo cubre el egreso de pago a proveedor (PROC-CTB-003); `tipo`/`concepto`
quedan abiertos para futuros movimientos (otros egresos, ingresos).

`comprobante_id` es único cuando no es NULL — es el guardián de RN-CTB-008
(un mismo comprobante no se paga dos veces). `proveedor_id`/`orden_compra_id`
son UUID sin FK: son dominio de `purchases`, mismo criterio que
`Comprobante.compra_id` (nunca importar el dominio de otro módulo)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class MovimientoDinero(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "movimiento_dinero"
    __table_args__ = (UniqueConstraint("comprobante_id"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("egreso", "ingreso", name="tipo_movimiento_dinero", native_enum=False)
    )
    concepto: Mapped[str] = mapped_column(String(50))  # ej. "pago_proveedor"
    comprobante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comprobante.id"), nullable=True
    )
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    orden_compra_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    monto_detraccion: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Solo se define al ejecutar (RN-CTB-005/008).
    medio_pago: Mapped[str | None] = mapped_column(
        Enum(
            "transferencia", "cheque", "efectivo",
            name="medio_pago_movimiento_dinero", native_enum=False,
        ),
        nullable=True,
    )
    estado: Mapped[str] = mapped_column(
        Enum(
            "pendiente", "ejecutado", "rechazado",
            name="estado_movimiento_dinero", native_enum=False,
        ),
        default="pendiente",
    )
    solicitado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    aprobado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    asiento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("asiento.id"), nullable=True)
    fecha_ejecucion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    constancia: Mapped[str | None] = mapped_column(String(255), nullable=True)
