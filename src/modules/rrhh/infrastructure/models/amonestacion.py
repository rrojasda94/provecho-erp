"""Amonestación: escalón disciplinario previo a suspensión/despido
(RN-RRHH-004) — proporcionalidad, inmediatez, razonabilidad, non bis in idem,
derecho a descargo."""

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Amonestacion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "amonestacion"

    trabajador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trabajador.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("verbal", "escrita", name="tipo_amonestacion", native_enum=False)
    )
    falta: Mapped[str] = mapped_column(Text())
    fecha_hecho: Mapped[date] = mapped_column(Date())
    fecha_emision: Mapped[date] = mapped_column(Date())
    emisor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    descargo: Mapped[str | None] = mapped_column(Text(), nullable=True)
    descargo_plazo_dias: Mapped[int | None] = mapped_column(nullable=True)
    sancion_relacionada: Mapped[str | None] = mapped_column(String(200), nullable=True)
