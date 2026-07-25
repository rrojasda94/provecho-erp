"""refresh_token: token de refresco rotativo.

Se guarda solo el hash (SHA-256), nunca el token en claro. `sesion_id`
agrupa la cadena de rotación: reusar un token revocado revoca toda la
sesión (RN de seguridad del README de users).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class RefreshToken(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "refresh_token"

    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    sesion_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocado: Mapped[bool] = mapped_column(Boolean, default=False)
