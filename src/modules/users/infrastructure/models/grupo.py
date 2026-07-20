"""Grupo empresarial: nivel máximo de la organización."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Grupo(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "grupo"

    nombre: Mapped[str] = mapped_column(String(100), unique=True)
