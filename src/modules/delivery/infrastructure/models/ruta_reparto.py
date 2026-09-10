"""Ruta de reparto: una salida de un repartidor propio con una o más
paradas (ADR-098). Siempre vuelve al punto de origen.

`origen_lat`/`origen_lng` copian la ubicación de la sucursal **al crear**
la ruta, no la leen en vivo desde `sucursal` — si la sucursal se muda de
local (raro, pero ocurre en `docs/architecture/data-model.md`), la ruta ya
planificada no tiene por qué recalcular su punto de partida.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.modules.delivery.domain import rules


class RutaReparto(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "ruta_reparto"

    __table_args__ = (
        Index("ix_ruta_reparto_sucursal_estado", "sucursal_id", "estado"),
        Index("ix_ruta_reparto_repartidor_estado", "repartidor_id", "estado"),
        CheckConstraint(
            "estado IN ({})".format(", ".join(f"'{v}'" for v in rules.ESTADOS_RUTA)),
            name="estado_ruta_reparto",
        ),
        CheckConstraint(
            "optimizada_por IN ({})".format(", ".join(f"'{v}'" for v in rules.FUENTES_RUTEO)),
            name="optimizada_por_ruta_reparto",
        ),
    )

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    repartidor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repartidor.id"))
    creada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    estado: Mapped[str] = mapped_column(
        Enum(*rules.ESTADOS_RUTA, name="estado_ruta_reparto", native_enum=False),
        default="planificada",
    )
    hora_salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hora_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    origen_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    origen_lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    distancia_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duracion_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Sin polyline cuando se optimizó por heurística: sin llamada a Google
    # no hay geometría de ruta, solo el orden y la suma de tramos.
    polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    optimizada_por: Mapped[str] = mapped_column(
        Enum(*rules.FUENTES_RUTEO, name="optimizada_por_ruta_reparto", native_enum=False)
    )
    # Última posición conocida, denormalizada desde `posicion_repartidor`
    # (RN-DLV-007): el tablero y el enlace público la leen sin JOIN al
    # breadcrumb completo en cada refresco.
    ultima_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    ultima_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    ultima_precision_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ultima_posicion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
