"""SKU: código interno e inmutable de un artículo y sus variantes
intercambiables (marcas/proveedores). Un artículo puede tener varios.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Sku(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "sku"

    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    codigo_barras: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prioridad: Mapped[int] = mapped_column(Integer, default=1)
    # Baja lógica — nunca se elimina, es historial.
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
