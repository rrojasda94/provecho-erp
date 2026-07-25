"""rol_permiso: asignación N:M de permisos a roles (PK compuesta)."""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin


class RolPermiso(Base, TimestampMixin):
    __tablename__ = "rol_permiso"

    rol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rol.id"), primary_key=True)
    permiso_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permiso.id"), primary_key=True
    )
