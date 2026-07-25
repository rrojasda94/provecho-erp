"""usuario_sucursal: alcance del usuario por sucursal (PK compuesta).

Sin filas para un usuario = sin restricción de sucursal (ej. admin), según
resuelva la capa de autorización.
"""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin


class UsuarioSucursal(Base, TimestampMixin):
    __tablename__ = "usuario_sucursal"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuario.id"), primary_key=True
    )
    sucursal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sucursal.id"), primary_key=True
    )
