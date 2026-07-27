"""Socio: participación societaria a nivel grupo o empresa. No implica
`trabajador` ni `usuario` — se referencia en aprobaciones (RN-GRP-006,
RN-MAR-004)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Socio(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "socio"

    grupo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("grupo.id"), nullable=True)
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("empresa.id"), nullable=True)
    # Persona natural (persona_id) o jurídica (razon_social+ruc) — excluyentes,
    # igual convención que proveedor (RN-GEN-007).
    persona_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("persona.id"), nullable=True)
    razon_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ruc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    porcentaje_participacion: Mapped[Decimal] = mapped_column(Numeric(5, 2))
