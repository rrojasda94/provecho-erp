"""`sync_watermark`: hasta dónde sincronizó este hub, por recurso y dirección.

Única tabla que el motor de sync agrega al esquema (ADR-009, fase 2). Solo
la escribe un hub; en la nube queda vacía.

Por qué una tabla y no `max(updated_at)` local, como preveía la fase 1: el
hub **escribe** localmente algunas de las tablas que también replica
(`stock` se mueve solo con cada venta offline), así que su propio
`max(updated_at)` no dice nada sobre hasta dónde leyó de la nube. Y la
dirección ascendente necesita memoria durable de qué se empujó, que ningún
dato local tiene. No es un outbox (descartado en el ADR): es una fila por
recurso, no una por escritura.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin


class SyncWatermark(Base, TimestampMixin):
    __tablename__ = "sync_watermark"

    # `pull` (nube → hub) o `push` (hub → nube).
    direccion: Mapped[str] = mapped_column(String(10), primary_key=True)
    recurso: Mapped[str] = mapped_column(String(50), primary_key=True)
    # Último `campo_marca` procesado. NULL = nunca sincronizó (carga inicial).
    marca: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_ok: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Diagnóstico para `/health/sync`: un recurso que falla siempre frena su
    # watermark, y sin esto el operador no tendría cómo enterarse.
    ultimo_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
