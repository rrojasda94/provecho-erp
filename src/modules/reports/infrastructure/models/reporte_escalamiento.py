"""La cadena de escalamiento de un reporte (RN-CTP-004, ADR-036).

Un reporte decía qué pasó y ahí moría. Cuando quien lo recibe no puede
resolverlo —una queja que no le corresponde, una no conformidad que necesita
decisión de Gerencia— no había dónde dejar constancia de que se elevó, a
quién, ni qué se hizo en cada nivel.

**Ancla a `reporte_emitido`, no a la venta.** El spec original
(`data-model.md` §6) hablaba de `venta_id | carrito_id | orden_produccion_id`;
esas tres claves son exactamente lo que `reporte_emitido.referencia_tipo` +
`referencia_id` ya guardan, para los nueve tipos y no para tres — y `carrito`
ni siquiera existe como tabla. Anclar a la venta además perdería la foto
`datos`, el `nivel`, el `actor_id` y la doble puerta de RN-REP-002.

**`acciones` es append-only** (RN-REP-012): el historial por nivel es el
insumo de la mejora continua del área Comercial, y un nivel que reescribe lo
que dijo el anterior convierte el registro en la versión del último que pasó.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class ReporteEscalamiento(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "reporte_escalamiento"
    __table_args__ = (
        # Un reporte, una cadena abierta (RN-REP-013). Dos cadenas sobre el
        # mismo hecho dan dos verdades y dos responsables.
        #
        # Índice parcial y no `UniqueConstraint`: las cerradas tienen que
        # poder convivir, y la convención `uq_%(table_name)s_%(column_0_name)s`
        # de `core/database.py` haría chocar el nombre con cualquier otro
        # UNIQUE que empiece por la misma columna — el bug de `guia_remision`
        # (CHANGELOG 2026-08-06).
        Index(
            "uq_escalamiento_abierto_por_reporte",
            "reporte_emitido_id",
            unique=True,
            sqlite_where=text(
                "estado NOT IN ('resuelto_supervisor', 'resuelto', 'cerrado')"
            ),
            postgresql_where=text(
                "estado NOT IN ('resuelto_supervisor', 'resuelto', 'cerrado')"
            ),
        ),
        # "Qué tengo pendiente en mi nivel": la pantalla del que responde.
        Index(
            "ix_reporte_escalamiento_pendientes",
            "empresa_id",
            "nivel_actual",
            "estado",
        ),
        Index("ix_reporte_escalamiento_empresa", "empresa_id", "created_at"),
        CheckConstraint(
            "(estado NOT IN ('resuelto_supervisor', 'resuelto', 'cerrado')) "
            "OR (cerrado_at IS NOT NULL)",
            name="ck_reporte_escalamiento_cierre_fechado",
        ),
    )

    # Desnormalizada y NOT NULL: filtrar por tenant sin join, y un reporte que
    # no se pudo atribuir a una empresa no se escala (RN-REP-011) — no habría
    # a qué área elevarlo.
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Nula en hechos de ámbito empresa (un pago sobre umbral).
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    # `RESTRICT` y no `CASCADE` (que sí usa `entrega_reporte`): el reporte es
    # la evidencia de la cadena, y borrarlo dejaría acciones sin el hecho que
    # las provocó.
    reporte_emitido_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reporte_emitido.id", ondelete="RESTRICT"), index=True
    )
    origen: Mapped[str] = mapped_column(
        Enum(
            "central_pedidos",
            "punto_venta",
            "produccion",
            name="origen_escalamiento",
            native_enum=False,
        )
    )
    motivo: Mapped[str] = mapped_column(
        Enum(
            "queja",
            "demora",
            "error_sistema",
            "desistimiento_no_resuelto",
            "no_conformidad_calidad",
            name="motivo_escalamiento",
            native_enum=False,
        )
    )
    descripcion: Mapped[str] = mapped_column(Text)
    reportado_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # Obligatoria si el motivo es no conformidad y la orden terminó en desecho
    # (RN-PRD-015). La regla se valida en `application/escalamientos.py` y no
    # acá: "terminó en desecho" vive en `orden_produccion.resultado`, otra
    # tabla de otro módulo — mismo criterio que `decision_gerencial.condiciones`.
    evidencia_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("archivo.id"), nullable=True
    )
    nivel_actual: Mapped[str] = mapped_column(
        Enum(
            "supervisor",
            "comercial",
            "gerencia",
            name="nivel_escalamiento",
            native_enum=False,
        ),
        default="supervisor",
    )
    estado: Mapped[str] = mapped_column(
        Enum(
            "abierto",
            "resuelto_supervisor",
            "escalado",
            "resuelto",
            "cerrado",
            name="estado_escalamiento",
            native_enum=False,
        ),
        default="abierto",
    )
    # `[{nivel, usuario_id, accion, descripcion, ts}]`, en orden. Nunca se
    # reescribe una entrada: se agrega (RN-REP-012).
    acciones: Mapped[list] = mapped_column(JsonB, default=list)
    cerrado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
