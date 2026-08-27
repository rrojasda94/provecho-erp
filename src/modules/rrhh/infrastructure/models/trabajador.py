"""Trabajador: persona con vínculo laboral (planilla) en una empresa.

Distinto de `usuario` (identidad de login): un trabajador puede o no
tener usuario, y no todo usuario es trabajador (ej. agente_ia).

`usuario_id` NO es columna propia (ADR-069): se deriva de `persona_id`. La
cuenta de un trabajador es la del `usuario` cuya `persona_id` es la suya —
una sola arista, vinculada desde Usuarios. Antes había dos columnas
(`usuario.persona_id` y `trabajador.usuario_id`) que nadie sincronizaba:
vincular la persona desde Usuarios no habilitaba el pad de asistencia, que
solo leía esta columna.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String, select
from sqlalchemy.orm import Mapped, column_property, declared_attr, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin
from src.modules.users.infrastructure.models import Usuario


class Trabajador(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "trabajador"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persona.id"))
    # Centro de labores: dónde trabaja, no qué datos alcanza (ADR-062). El
    # alcance de acceso vive en `usuario_sucursal`, del lado de la cuenta.
    # Nullable: gerencia y administración no están en ningún local.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )

    # Derivado, no columna (ADR-069): la cuenta con la que este trabajador
    # marca en el pad es la del `usuario` cuya `persona_id` coincide con la
    # suya. Subconsulta con LIMIT 1 y no `relationship(viewonly=True,
    # lazy="joined")` a propósito: con dos usuarios sobre una persona (que el
    # índice único evita, pero un dato viejo podría tener) el joined eager
    # load duplica la fila padre en silencio y `paginar` contaría de más.
    # Una persona puede tener más de una fila `trabajador` (recontratación:
    # una cesada + una activa) — las dos comparten esta misma cuenta.
    @declared_attr
    def usuario_id(cls) -> Mapped[uuid.UUID | None]:
        return column_property(
            select(Usuario.id)
            .where(
                Usuario.persona_id == cls.persona_id,
                Usuario.deleted_at.is_(None),
            )
            .limit(1)
            .correlate_except(Usuario)
            .scalar_subquery()
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
