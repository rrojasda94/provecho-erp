"""Refresh token de una cuenta del sitio: mismo mecanismo de rotación y
detección de reuso que `users.refresh_token` (ADR-102), sobre su propia
tabla — nunca comparte fila con el refresh token del ERP."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class StorefrontRefreshToken(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "storefront_refresh_token"

    cuenta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("storefront_cuenta.id"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    sesion_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocado: Mapped[bool] = mapped_column(Boolean, default=False)
