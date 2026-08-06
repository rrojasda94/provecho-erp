"""POS de pago con tarjeta, inventariado por contabilidad (RN-POS-010).

Existe porque el POS es el otro lado del cobro: el cierre de caja cuadra
contra el reporte de lote de cada terminal, y sin saber qué terminales hay
en la sucursal no se puede exigir ese reporte ni detectar que uno lleva
días averiado.

`sucursal_id` en NULL identifica al terminal de reserva que contabilidad
mantiene para cubrir fallas o picos de demanda (RN-POS-009): no pertenece a
una sucursal, se presta a la que lo necesite.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class PosTarjeta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "pos_tarjeta"
    __table_args__ = (UniqueConstraint("serie", name="uq_pos_tarjeta_serie"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # NULL = terminal de emergencia del pool de contabilidad (RN-POS-009).
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    # Los dos datos con los que el operador identifica el terminal en su
    # liquidación; sin ellos el reporte de lote no se puede conciliar.
    serie: Mapped[str] = mapped_column(String(50))
    codigo_comercio: Mapped[str] = mapped_column(String(50))
    operador: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "operativo",
            "averiado",
            "baja",
            name="estado_pos_tarjeta",
            native_enum=False,
        ),
        default="operativo",
    )
    es_emergencia: Mapped[bool] = mapped_column(Boolean, default=False)
