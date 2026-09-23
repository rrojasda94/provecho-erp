"""Dirección de envío guardada por una cuenta del sitio (ADR-104). El
cliente puede tener varias, nombrarlas y elegir una por defecto."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UbicacionMixin, UuidPkMixin


class StorefrontDireccion(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin, UbicacionMixin):
    __tablename__ = "storefront_direccion"

    cuenta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("storefront_cuenta.id"), index=True
    )
    # "Casa", "Trabajo" — libre, nunca obligatorio.
    etiqueta: Mapped[str | None] = mapped_column(String(50), nullable=True)
    direccion: Mapped[str] = mapped_column(String(255))
    referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    predeterminada: Mapped[bool] = mapped_column(Boolean, default=False)
