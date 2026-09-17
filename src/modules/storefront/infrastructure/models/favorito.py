"""Favorito: un producto comercial que una cuenta marcó para volver rápido
(ADR-102). `producto_comercial_id` es cross-módulo (`sales`) a nivel de FK
de base de datos — el límite de import es de la capa de aplicación, no del
esquema (mismo patrón que `producto_comercial.empaque_id` → `articulo`)."""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class StorefrontFavorito(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "storefront_favorito"
    __table_args__ = (UniqueConstraint("cuenta_id", "producto_comercial_id"),)

    cuenta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("storefront_cuenta.id"), index=True
    )
    producto_comercial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("producto_comercial.id")
    )
