"""Recepción de una OC (total o parcial). `comprobante_id` es el sustento
(RN-CMP-005) — opcional en este slice porque `purchases` aún no emite el
`comprobante` recibido (deuda técnica: conformidad → `comprobante_conforme`
→ `accounting` ejecuta el pago)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class RecepcionCompra(Base, UuidPkMixin):
    __tablename__ = "recepcion_compra"

    orden_compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_compra.id"))
    comprobante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comprobante.id"), nullable=True
    )
    recibido_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
