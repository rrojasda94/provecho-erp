"""Breadcrumb de GPS de una ruta en curso (ADR-098). Sin agregación: cada
ping es una fila, y `ruta_reparto.ultima_*` guarda la denormalización que
lee el tablero y el enlace público sin recorrer el trazo completo.

`registrado_at` es el reloj del teléfono, no `created_at` (que es cuándo
llegó al servidor): con la red del reparto yendo y viniendo, los pings
pueden llegar fuera de orden, y lo que ordena el trazo es cuándo ocurrió
de verdad, no cuándo se enteró el servidor.

Se purga a los 30 días (`delivery_posiciones_retencion_dias`, Celery
beat) — es rastro operativo, no un libro contable.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class PosicionRepartidor(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "posicion_repartidor"

    __table_args__ = (Index("ix_posicion_repartidor_ruta_registrado", "ruta_id", "registrado_at"),)

    ruta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ruta_reparto.id"))
    repartidor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repartidor.id"))
    lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    precision_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registrado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
