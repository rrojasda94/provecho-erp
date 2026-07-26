"""Acta: constancia formal de un hecho (reunión, incidente, entrega de
cargo, arqueo, verificación)."""

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class Acta(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "acta"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    tipo: Mapped[str] = mapped_column(
        Enum(
            "reunion", "incidente", "entrega_cargo", "arqueo", "verificacion",
            name="tipo_acta", native_enum=False,
        )
    )
    fecha: Mapped[date] = mapped_column(Date())
    lugar: Mapped[str] = mapped_column(String(200))
    hechos: Mapped[str] = mapped_column(Text())
    # [{persona_id | nombre, firma: bool}, ...]
    participantes: Mapped[list] = mapped_column(JsonB)
