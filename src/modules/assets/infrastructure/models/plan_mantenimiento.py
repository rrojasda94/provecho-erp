"""Plan de mantenimiento: la frecuencia recomendada de un activo (RN-MNT-001)
y el aviso con anticipación configurable (RN-MNT-005)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.modules.assets.domain.rules import (
    DIAS_AVISO_MANTENIMIENTO_DEFECTO,
    KM_AVISO_MANTENIMIENTO_DEFECTO,
)


class PlanMantenimiento(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "plan_mantenimiento"

    __table_args__ = (
        # Al menos una frecuencia declarada — sin ninguna, el plan no vence
        # nunca y el barrido no tendría qué evaluar.
        CheckConstraint(
            "cada_dias IS NOT NULL OR cada_km IS NOT NULL",
            name="plan_mantenimiento_frecuencia",
        ),
    )

    activo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activo.id"))
    nombre: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    cada_dias: Mapped[int | None] = mapped_column(nullable=True)
    # Solo tiene sentido si `activo.tipo == "vehiculo"` — se valida en el
    # dominio, no acá (un CHECK no puede mirar la tabla `activo`).
    cada_km: Mapped[int | None] = mapped_column(nullable=True)
    dias_aviso: Mapped[int] = mapped_column(default=DIAS_AVISO_MANTENIMIENTO_DEFECTO)
    km_aviso: Mapped[int] = mapped_column(default=KM_AVISO_MANTENIMIENTO_DEFECTO)
    # Sin FK: `proveedor` es dominio de `purchases`.
    proveedor_servicio_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Punto de partida cuando el plan todavía no se ejecutó ni una vez: el
    # kilometraje del vehículo al crear el plan. Sin esto, un vehículo que ya
    # traía kilometraje alto contaría el ciclo desde 0 y avisaría de
    # inmediato.
    km_base: Mapped[int | None] = mapped_column(nullable=True)
    ultima_fecha: Mapped[date | None] = mapped_column(Date, nullable=True)
    ultimo_km: Mapped[int | None] = mapped_column(nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Idempotencia del barrido (`assets.barrer_vencimientos`): la fecha en que
    # se publicó cada aviso, para no repetirlo cada corrida mientras el plan
    # siga en la misma ventana. Se limpian al realizar la orden.
    aviso_proximo_en: Mapped[date | None] = mapped_column(Date, nullable=True)
    aviso_vencido_en: Mapped[date | None] = mapped_column(Date, nullable=True)
