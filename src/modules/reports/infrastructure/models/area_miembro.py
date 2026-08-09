"""Quién compone un área: roles y/o personas puntuales.

Por **rol** es lo que se administra solo — alguien cambia de puesto y gana o
pierde los reportes del área sin que nadie recuerde actualizar una lista, y
quien cesa deja de recibirlos al perder el rol. Mismo criterio que el
addendum de ADR-024 para compartir tableros.

Por **usuario** existe igual porque hay excepciones reales que no son un rol:
el dueño que quiere ver los descuadres de un solo local. Forzar un rol para
eso llenaría el RBAC de roles de una persona.

`sucursal_id` acota la membresía: «el almacenero de Tarapoto es del área
Almacén, pero solo para lo que pasa en Tarapoto». Nulo = en toda la empresa.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class AreaMiembro(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "area_miembro"
    __table_args__ = (
        # Uno u otro, nunca los dos ni ninguno: una fila con rol *y* usuario
        # no significa nada, y una con ninguno es una membresía vacía que
        # resolvería a cero destinatarios sin que se note.
        CheckConstraint(
            "(rol_id IS NULL) <> (usuario_id IS NULL)",
            name="ck_area_miembro_rol_o_usuario",
        ),
    )

    area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("area.id"), index=True)
    rol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rol.id"), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    # Nulo = la membresía vale en toda la empresa.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
