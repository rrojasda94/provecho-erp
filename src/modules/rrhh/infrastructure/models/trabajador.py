"""Trabajador: persona con vínculo laboral (planilla) en una empresa.

Distinto de `usuario` (identidad de login): un trabajador puede o no
tener usuario, y no todo usuario es trabajador (ej. agente_ia).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Trabajador(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "trabajador"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persona.id"))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    cargo: Mapped[str] = mapped_column(String(100))
    area: Mapped[str] = mapped_column(String(100))
    tipo_vinculo: Mapped[str] = mapped_column(
        Enum(
            "planilla",
            "practicante",
            "locacion_servicios",
            name="tipo_vinculo_trabajador",
            native_enum=False,
        )
    )
    regimen_laboral: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fecha_ingreso: Mapped[date] = mapped_column()
    fecha_cese: Mapped[date | None] = mapped_column(nullable=True)
    # O subvención si tipo_vinculo=practicante (RN-PER-001).
    remuneracion_base: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    sistema_pensiones: Mapped[str | None] = mapped_column(
        Enum("onp", "afp", name="sistema_pensiones", native_enum=False),
        nullable=True,
    )
    afp_nombre: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tiene_poderes: Mapped[bool] = mapped_column(Boolean, default=False)
    # Siempre False si tipo_vinculo=locacion_servicios (RN-PER-002) —
    # se valida en el dominio, no aquí.
    registra_asistencia: Mapped[bool] = mapped_column(Boolean, default=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "activo",
            "cesado",
            "suspendido",
            name="estado_trabajador",
            native_enum=False,
        ),
        default="activo",
    )
