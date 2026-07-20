"""Cliente: transversal al grupo, no a una empresa (RN-PTS-001).

Natural (liga a persona) o jurídico (razón social + RUC propios).
`cliente_id` es opcional en `venta` — cliente anónimo es válido
(RN-PER-005).

`usuario_id` es opcional (2026-07-20, decisión del usuario): cuenta propia
solo para autoservicio web (ver historial, pedir online) — comprar en
sucursal o por Central de Pedidos NUNCA exige login, esas ventas igual
enrutan al mismo `cliente` por sus datos (persona/contacto).
"""

import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Cliente(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cliente"

    grupo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grupo.id"))
    tipo: Mapped[str] = mapped_column(
        Enum("natural", "juridico", name="tipo_cliente", native_enum=False)
    )
    # Si tipo=natural — nombre/documento se leen de persona (RN-GEN-007).
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("persona.id"), nullable=True
    )
    # Si tipo=juridico (cliente corporativo: catering, eventos).
    razon_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ruc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    contacto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Cuenta de autoservicio web — opcional, NUNCA requerida para comprar
    # en sucursal/Central de Pedidos. Un usuario es de a lo más un cliente.
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), unique=True, nullable=True
    )
