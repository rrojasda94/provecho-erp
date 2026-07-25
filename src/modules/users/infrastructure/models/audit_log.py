"""audit_log: rastro inmutable de cambios (quién, qué, cuándo, dónde,
valor antes/después). Solo inserción — no se actualiza ni se borra.

Distinto de la entidad `auditoria` (proceso de evaluación). Consumido por
todos los módulos vía core.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, UuidPkMixin


class AuditLog(Base, UuidPkMixin):
    __tablename__ = "audit_log"

    # NULL para acciones del sistema (sin usuario autenticado).
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    entidad: Mapped[str] = mapped_column(String(100))
    entidad_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    accion: Mapped[str] = mapped_column(String(50))
    datos_antes: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    datos_despues: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
