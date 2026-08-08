"""Marca: enseña comercial; la identidad pertenece al grupo, no a una empresa."""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Marca(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "marca"
    __table_args__ = (UniqueConstraint("grupo_id", "nombre"),)

    grupo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grupo.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    # Extensible (restaurante, delivery, servicio, ...) — String a propósito.
    tipo: Mapped[str] = mapped_column(String(50))
    # Skins de marca para la TPV (branding por marca en el PDV).
    skins: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
