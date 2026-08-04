"""Notificación: un aviso dirigido a una persona concreta.

Vive en `users` porque su dueño es el destinatario, no el hecho que la
originó: la misma tabla sirve para una alerta de cocina, un stock bajo
mínimo o un parámetro esperando aprobación de Gerencia.

Es **bandeja, no transporte**: la fila se crea siempre y el frontend la
consulta. Empujarla a un teléfono (push, WhatsApp) es una capa aparte que
todavía no existe — y cuando exista, leerá de acá en vez de reemplazarla,
porque un aviso que solo viajó por push no deja rastro de si alguien lo vio.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

# Severidad: qué tan fuerte se muestra. No es el tipo del hecho, es cuánto
# interrumpe — un mismo tipo puede ser aviso o urgencia según el dato.
NIVELES = ("info", "aviso", "urgente")


class Notificacion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "notificacion"
    __table_args__ = (
        # La consulta que corre en cada carga de pantalla: "mis no leídas".
        Index("ix_notificacion_bandeja", "usuario_id", "leida_at"),
    )

    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Código del hecho (`sales.pedido_demorado`, …): el frontend agrupa e
    # iconiza por esto, y el día que haya preferencias de aviso, se filtra
    # por acá.
    tipo: Mapped[str] = mapped_column(String(60))
    nivel: Mapped[str] = mapped_column(String(10), default="aviso")
    titulo: Mapped[str] = mapped_column(String(150))
    cuerpo: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A qué apunta, sin FK: la notificación es transversal y no puede tener
    # una FK a `venta`, `alerta_pedido` y todo lo que venga. Mismo criterio
    # que `decision_gerencial.referencia_tipo/id`.
    referencia_tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Para escopar la bandeja por local sin resolver la referencia.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )

    leida_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
