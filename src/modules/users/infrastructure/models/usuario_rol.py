"""usuario_rol: asignación N:M de roles a usuarios (PK compuesta)."""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin


class UsuarioRol(Base, TimestampMixin):
    __tablename__ = "usuario_rol"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuario.id"), primary_key=True
    )
    rol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rol.id"), primary_key=True)
