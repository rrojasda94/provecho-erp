"""audit_log: rastro inmutable de cambios (quién, qué, cuándo, dónde,
valor antes/después). Solo inserción — no se actualiza ni se borra.

Transversal por definición: la tabla no es de ningún módulo (ADR-029).
Vivía en `users` por historia —ahí nació el primer registro auditado—, y
eso obligaba a `rrhh` (y a cualquier otro módulo que quisiera dejar rastro)
a importar los repositorios de `users`. Se escribe siempre por
`src.shared.auditoria.registrar`, nunca instanciando este modelo.

Distinto de la entidad `auditoria` (proceso de evaluación, data-model §2).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, UuidPkMixin


class AuditLog(Base, UuidPkMixin):
    __tablename__ = "audit_log"
    __table_args__ = (
        # "Todo lo que le pasó a esta venta": la consulta de la ficha.
        Index("ix_audit_log_entidad", "entidad", "entidad_id"),
        # "Qué se tocó ayer": el listado por defecto, siempre por fecha.
        Index("ix_audit_log_ts", "ts"),
    )

    # NULL para acciones del sistema (sin usuario autenticado).
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    entidad: Mapped[str] = mapped_column(String(100))
    entidad_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    accion: Mapped[str] = mapped_column(String(50))
    datos_antes: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    datos_despues: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # Tenant del hecho (ADR-004): con qué alcance puede leerse la fila.
    # Ambos nullable porque no todo hecho auditable tiene local o empresa —
    # un login fallido no los tiene todavía, y un alta de rol es global.
    # Una fila sin ninguno de los dos solo la ve un superusuario.
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("empresa.id"), nullable=True
    )
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
