"""Encuesta de satisfacción: selectiva, nunca automática para toda venta
(RN-COM-007). Su disparador es `sales.venta_entregada` (PROC-OPE-002)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class EncuestaSatisfaccion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "encuesta_satisfaccion"
    # Una encuesta por venta: reenviar no crea otra fila.
    __table_args__ = (UniqueConstraint("venta_id"),)

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"))
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cliente.id"))
    canal: Mapped[str] = mapped_column(
        Enum("pos", "whatsapp", "link", name="canal_encuesta", native_enum=False)
    )
    fecha_envio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_respuesta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    puntaje: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comentario: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum("enviada", "respondida", "expirada", name="estado_encuesta", native_enum=False),
        default="enviada",
    )
    enviada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
