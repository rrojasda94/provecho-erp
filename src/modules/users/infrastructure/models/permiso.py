"""Permiso: código `modulo.accion` (ej. `sales.crear`, `inventory.transferir`).

`codigo = "*"` habilita todo (solo rol admin en entornos internos).
`restricciones` (JSONB) acota el permiso: por alcance, monto, estado, horario.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Permiso(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "permiso"

    codigo: Mapped[str] = mapped_column(String(100), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    restricciones: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
