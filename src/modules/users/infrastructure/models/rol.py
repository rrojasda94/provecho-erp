"""Rol: agrupa permisos (admin, supervisor, cajero, almacenero, agente_ia...)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Rol(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "rol"

    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
