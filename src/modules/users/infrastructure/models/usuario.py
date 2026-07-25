"""Usuario: identidad que se autentica. Tipo humano (liga a persona) o
agente_ia (sin persona).

Alcance mínimo para este slice — RBAC completo (rol, permiso,
usuario_rol, rol_permiso, refresh_token, audit_log) se modela en el
slice dedicado de auth (data-model.md §2).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Usuario(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "usuario"

    username: Mapped[str] = mapped_column(String(50), unique=True)
    pin_hash: Mapped[str] = mapped_column(String(255))
    # NULL si tipo=agente_ia.
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("persona.id"), nullable=True
    )
    # Fallback de nombre para agente_ia (sin persona).
    nombre_display: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tipo: Mapped[str] = mapped_column(
        Enum("humano", "agente_ia", name="tipo_usuario", native_enum=False)
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Lockout: 5 intentos fallidos en ventana de 15 min bloquean el login.
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
