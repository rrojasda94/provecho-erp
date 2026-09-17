"""Categoría de tarea de supervisión (limpieza, apertura, mantenimiento...):
el supervisor las crea libremente, no hay catálogo cerrado en código."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class CategoriaTarea(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "categoria_tarea"

    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    nombre: Mapped[str] = mapped_column(String(80))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
