"""A quién apunta una regla: un área, un rol, un usuario o un resolutor.

Cuatro tipos y no uno solo porque los cuatro existen en la operación real:
el área (`almacen`), el rol suelto que no justifica un área (`contador`), la
persona puntual (el dueño), y el **dinámico** — el que no se puede listar de
antemano porque depende del momento: quién está de turno ahora, quién
responde por este almacén. Los dos dinámicos que hay
(`DINAMICOS` en `domain/catalogo.py`) son las funciones que vivían en
`users.application.notificaciones` y se mudaron acá con el módulo.
"""

import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class ReglaDestinatario(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "regla_destinatario"
    __table_args__ = (
        # Exactamente una referencia poblada, y la que corresponde al tipo.
        # Sin esto una fila `tipo=area` con `area_id` nulo resolvería a cero
        # destinatarios en silencio, que es el modo de fallar más caro que
        # tiene este módulo.
        CheckConstraint(
            "(tipo = 'area'     AND area_id     IS NOT NULL) OR "
            "(tipo = 'rol'      AND rol_id      IS NOT NULL) OR "
            "(tipo = 'usuario'  AND usuario_id  IS NOT NULL) OR "
            "(tipo = 'dinamico' AND dinamico    IS NOT NULL)",
            name="ck_regla_destinatario_referencia",
        ),
    )

    regla_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("regla_distribucion.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[str] = mapped_column(
        Enum(
            "area",
            "rol",
            "usuario",
            "dinamico",
            name="tipo_destinatario",
            native_enum=False,
        )
    )
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("area.id"), nullable=True
    )
    rol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rol.id"), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    # `encargado_de_turno` | `responsables_de_almacen`.
    dinamico: Mapped[str | None] = mapped_column(String(40), nullable=True)
