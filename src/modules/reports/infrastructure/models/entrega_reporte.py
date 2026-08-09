"""A quién le tocó un reporte y **por qué**.

El «por qué» (`motivo`: `area:almacen`, `rol:supervisor`,
`dinamico:encargado_de_turno`) es la mitad del valor del hub. Sin él la
matriz dice quién recibe pero no qué hay que tocar para cambiarlo, que es
justamente el trabajo que este módulo viene a facilitar.

**No lleva `leida_at`.** El estado de lectura ya vive en
`notificacion.leida_at`, que es la bandeja que el usuario abre. Duplicarlo
acá daría dos verdades sobre el mismo hecho y se separarían en la primera
entrega que falle a medias. Esta tabla registra la *distribución*; la
lectura la registra la bandeja.
"""

import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class EntregaReporte(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "entrega_reporte"
    __table_args__ = (
        # Una entrega por persona y reporte: alguien que está en el área
        # Almacén *y* es el encargado de turno recibe una vez, no dos.
        UniqueConstraint(
            "reporte_emitido_id", "usuario_id", name="uq_entrega_reporte_usuario"
        ),
        # La consulta de `/mios`.
        Index("ix_entrega_usuario", "usuario_id"),
    )

    reporte_emitido_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reporte_emitido.id", ondelete="CASCADE"), index=True
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # `area:almacen`, `rol:supervisor`, `usuario`, `dinamico:encargado_de_turno`.
    # Se congela al emitir (RN-REP-004): si mañana sacan a esta persona del
    # área, el registro tiene que seguir explicando por qué lo recibió.
    motivo: Mapped[str] = mapped_column(String(60))
    canal: Mapped[str] = mapped_column(
        Enum("bandeja", name="canal_entrega", native_enum=False), default="bandeja"
    )
