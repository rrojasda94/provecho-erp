"""Encuesta de satisfacción: selectiva, nunca automática para toda venta
(RN-COM-007). Su disparador es `sales.venta_entregada` (PROC-OPE-002).

La fila es además el **estado de una conversación**: `pregunta_actual_id`
dice en qué nodo del guion está el cliente, y sin eso una respuesta suelta
que llega por WhatsApp no se puede interpretar (¿es el puntaje o el
comentario?). El detalle nodo por nodo vive en `encuesta_respuesta`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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

    # --- Conversación por nodos ---------------------------------------------
    # NULL solo en las encuestas anteriores al guion (2026-08-08): esas se
    # responden con un puntaje suelto y no tienen nodos que recorrer.
    plantilla_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("encuesta_plantilla.id"), nullable=True
    )
    # En qué nodo está el cliente. NULL con estado `enviada` = todavía no se
    # despachó el primer mensaje; NULL con `respondida` = llegó al final.
    pregunta_actual_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("encuesta_pregunta.id"), nullable=True
    )
    # A dónde se mandó: teléfono E.164 en WhatsApp, vacío en `pos`.
    # Indexado: el webhook busca por acá la encuesta abierta en **cada**
    # mensaje que llega; sin índice es un scan de toda la tabla por cada "sí".
    destino: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    # Meta solo acepta plantillas aprobadas fuera de la ventana de 24 h. El
    # primer mensaje es esa plantilla; recién cuando el cliente contesta
    # cualquier cosa se abre la ventana y empiezan las preguntas. Este flag
    # distingue "todavía no contestó nunca" de "está a mitad del guion", que
    # es lo que decide si su mensaje es una respuesta o un simple "hola".
    conversacion_abierta: Mapped[bool] = mapped_column(Boolean, default=False)
    # Secreto del enlace público: es la única credencial del cliente, que no
    # tiene usuario en el ERP. Único para que la URL identifique la encuesta.
    token_publico: Mapped[str] = mapped_column(String(64), unique=True)
    fecha_expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Acuse del canal: id del mensaje en Meta y el último fallo de envío, que
    # es lo que distingue "el cliente no contestó" de "nunca le llegó".
    mensaje_externo_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_envio: Mapped[str | None] = mapped_column(String(255), nullable=True)
