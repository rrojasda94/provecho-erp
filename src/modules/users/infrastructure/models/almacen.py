"""Almacén: contenedor de stock (central, producción, sucursal, activos)."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Almacen(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "almacen"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # NULL si es central, de producción o virtual de activos.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(100))
    # Enum extensible (ej. futuro `transporte` como hub físico, RN-TRP-003)
    # — String a propósito. `activos` es virtual, sin stock de SKUs.
    tipo: Mapped[str] = mapped_column(String(30))
    # El central del que se abastece un almacén de sucursal/producción.
    almacen_abastecedor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("almacen.id"), nullable=True
    )
