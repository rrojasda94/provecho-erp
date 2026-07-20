"""Licencia de marca: N:N empresa↔marca (modelo franquicia interna).

Pendiente de negocio: condiciones/regalías (ver data-model §1).
"""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class LicenciaMarca(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "licencia_marca"
    __table_args__ = (UniqueConstraint("empresa_id", "marca_id"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"))
