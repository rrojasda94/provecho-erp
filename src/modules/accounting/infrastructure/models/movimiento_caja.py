"""Ingreso o retiro de efectivo del cajón durante el turno (RN-MDP-007).

Existe porque el turno real no es solo vender: se paga al repartidor, se
compra hielo, entra un vuelto que faltaba. Sin registrar esos movimientos
el cierre cuadra contra un esperado irreal y todo descuadre se le atribuye
al cajero.

Distinto de `movimiento_dinero`, que es tesorería (pagos a proveedor desde
banco). Esto es exclusivamente el efectivo físico de UNA apertura de caja.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class MovimientoCaja(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "movimiento_caja"

    # El cierre suma todos los movimientos de su apertura: se consulta por
    # esta columna en cada cierre y en cada arqueo.
    apertura_caja_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("apertura_caja.id"), index=True
    )
    tipo: Mapped[str] = mapped_column(
        Enum("ingreso", "retiro", name="tipo_movimiento_caja", native_enum=False)
    )
    # Siempre positivo: el signo lo da `tipo`. Guardar negativos invita a
    # sumar mal en cuanto alguien olvide el valor absoluto.
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Obligatorio: un movimiento de efectivo sin motivo es indistinguible
    # de un faltante.
    motivo: Mapped[str] = mapped_column(String(120))
    registrado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Retirar plata del cajón lo autoriza un supervisor, no el cajero solo
    # (RN-MDP-007). NULL en los ingresos, que no requieren autorización.
    autorizado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
