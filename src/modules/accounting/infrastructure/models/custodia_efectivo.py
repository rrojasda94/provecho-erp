"""Custodia de efectivo: cadena cajero → encargado/supervisor →
contabilidad (RN-MDP-002). Cada transición exige confirmación de
valores correctos por el receptor (validado en el dominio).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class CustodiaEfectivo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "custodia_efectivo"

    apertura_caja_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apertura_caja.id"))
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    responsable_actual_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    estado: Mapped[str] = mapped_column(
        Enum(
            "en_caja",
            "en_supervisor",
            "en_contabilidad",
            "disponible",
            name="estado_custodia_efectivo",
            native_enum=False,
        ),
        default="en_caja",
    )
    # Lista de {rol, usuario_id, timestamp} — un registro por relevo.
    timestamps_relevo: Mapped[list | None] = mapped_column(JsonB, nullable=True)
