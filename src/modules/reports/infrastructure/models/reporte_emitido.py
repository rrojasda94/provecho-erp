"""El reporte que el ERP generó a partir de un hecho.

Es una **foto, no un puntero**. `datos` guarda los campos que la emisión
declara, tal como estaban al emitir: un reporte de «descuadre de S/ 40» tiene
que seguir diciendo 40 aunque el cierre se reabra y se corrija después. Ese
es todo el punto de guardarlo en vez de recalcularlo — para recalcular ya
está `core/reportes` (ADR-024).

Se persiste **aunque no tenga destinatarios** (RN-REP-005). Antes de este
módulo, un aviso sin a quién mandarlo era un `log.warning` que nadie leía;
acá queda como fila y sale marcado como hueco en la matriz.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class ReporteEmitido(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "reporte_emitido"
    __table_args__ = (
        # El listado del hub: los de mi empresa, más recientes primero.
        Index("ix_reporte_emitido_empresa", "empresa_id", "emitido_at"),
        # La columna de la matriz: cuántos y cuándo por emisión.
        Index("ix_reporte_emitido_codigo", "codigo_emision", "emitido_at"),
    )

    # Nulo solo si el hecho no pudo atribuirse a una empresa (un almacén
    # borrado, un payload incompleto). Se guarda igual: un reporte que no se
    # pudo escopar es justamente el que hay que poder investigar.
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("empresa.id"), nullable=True
    )
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    # De dónde viene, hasta el último nivel. `_ubicar()` ya lo resolvía para
    # elegir destinatarios y lo descartaba: sin él, un «stock bajo mínimo» no
    # dice en qué almacén hay que reponer.
    almacen_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("almacen.id"), nullable=True
    )
    # Quién provocó el hecho. Nulo = lo detectó el sistema (un barrido, un
    # cruce de umbral) y no hay a quién atribuírselo (RN-REP-009). Distinto de
    # `entrega_reporte.usuario_id`, que es a quién le *llegó*.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    codigo_emision: Mapped[str] = mapped_column(String(60))
    titulo: Mapped[str] = mapped_column(String(200))
    cuerpo: Mapped[str | None] = mapped_column(Text, nullable=True)
    nivel: Mapped[str] = mapped_column(
        Enum("info", "aviso", "urgente", name="nivel_reporte", native_enum=False),
        default="aviso",
    )
    # La foto: solo los campos que la emisión declara (RN-REP-003). Puede
    # traer PII (Ley 29733), así que no sale al logger — mismo criterio que
    # `audit_log.datos_antes/despues` (ADR-031).
    datos: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
    # A qué apunta, sin FK: el reporte es transversal y no puede tener una
    # FK a `venta`, `lote`, `cierre_caja` y todo lo que venga. Mismo criterio
    # que `notificacion.referencia_tipo/id`.
    referencia_tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Qué regla lo produjo. Nulo = ninguna aplicaba (el hueco). No se borra
    # ni se reescribe cuando la regla cambia: cambiar la distribución mañana
    # no puede reescribir a quién le llegó ayer (RN-REP-004).
    regla_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("regla_distribucion.id"), nullable=True
    )
    emitido_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
