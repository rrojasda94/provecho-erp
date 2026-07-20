"""Categoría de UdM (peso, volumen, distancia...) con su unidad base."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class CategoriaUdm(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "categoria_udm"

    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    # FK circular con unidad_medida — se crea con use_alter para que
    # Alembic pueda ordenar la creación de tablas.
    unidad_base_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("unidad_medida.id", use_alter=True), nullable=True
    )
