"""Lead de campaña. El valor de la campaña se mide por leads con `venta_id`
no nulo (conversión real), no por volumen bruto — RN-MKT-003."""

import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Lead(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "lead"

    campana_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campana.id"))
    canal: Mapped[str] = mapped_column(String(50))
    tipo: Mapped[str] = mapped_column(
        Enum("contacto", "visita", "cupon", "registro", name="tipo_lead", native_enum=False)
    )
    # Teléfono, correo o lo que dejó — texto libre, no toda pista trae cliente.
    contacto: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cliente.id"), nullable=True
    )
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venta.id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
