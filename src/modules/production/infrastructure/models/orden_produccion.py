"""Orden de producción: crear (borrador) → registrar consumo (en_proceso)
→ completar (conforme | no_conforme_reprocesado | no_conforme_desechado).

Costeo (RN-PRD-018) se calcula al completar, nunca a mano. La orden puede
nacer suelta (ad-hoc) o colgar de un `plan_produccion` (cronograma,
`plan_produccion_id`, bloque `feat/produccion-plan-de-produccion`).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class OrdenProduccion(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "orden_produccion"

    __table_args__ = (
        CheckConstraint(
            "estado IN ('borrador', 'en_proceso', 'conforme', "
            "'no_conforme_reprocesado', 'no_conforme_desechado')",
            name="estado_orden_produccion",
        ),
        CheckConstraint(
            "origen IN ('manual', 'ajuste_por_necesidad', 'plan')",
            name="origen_orden_produccion",
        ),
    )

    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    almacen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("almacen.id"))
    # Nullable: la mayoría de las órdenes de hoy siguen siendo ad-hoc, sin
    # plan. `application/planes.py::agregar_orden` la liga a un plan
    # `planificado`; al `iniciar` el plan se reservan sus insumos.
    plan_produccion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plan_produccion.id"), nullable=True
    )
    # `manual` (default, vía API) | `ajuste_por_necesidad` (la crea sola
    # `application/listeners.py` al cruzar `inventory.stock_bajo_minimo`,
    # RN-PRD-007/011) | `plan` (cronograma, diferido — ver ROADMAP).
    origen: Mapped[str] = mapped_column(
        Enum("manual", "ajuste_por_necesidad", "plan", name="origen_orden_produccion",
             native_enum=False),
        default="manual",
    )
    cantidad_planeada: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    cantidad_producida: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            "borrador",
            "en_proceso",
            "conforme",
            "no_conforme_reprocesado",
            "no_conforme_desechado",
            name="estado_orden_produccion",
            native_enum=False,
        ),
        default="borrador",
    )
    horas_hombre: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    # Cuándo cerró control de calidad (`completar_orden_produccion`), no
    # cuándo se tocó por última vez: `updated_at` se pisa con cada `flush`
    # (p. ej. `registrar_consumo`), así que no sirve para saber qué jornada
    # cerró la orden — `reportes_jornada.py` agrupa por esta columna
    # (bloque `feat/produccion-reporte-de-jornada`, RN-DOC-010).
    completado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Snapshot al registrar consumo (RN-PRD-018): lo que la receta BOM dice
    # que debería costar, escalada a `cantidad_planeada` — para comparar
    # contra `costo_insumos` (lo que de verdad se consumió) al completar. Sin
    # receta que produzca el artículo, queda NULL: no hay contra qué comparar.
    costo_teorico_insumos: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    costo_insumos: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    costo_mano_obra: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    costo_real_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    # Solo si estado=no_conforme_desechado (RN-PRD-015/018).
    merma_cantidad: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    merma_motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Reemplaza al string libre `evidencia_destruccion_url` desde
    # `feat/produccion-evidencia-como-archivo` (RN-PRD-015): la evidencia se
    # sube vía `POST /ordenes/{id}/evidencia` (`application/evidencia.py`,
    # mismo mecanismo que `marketing.application.adjuntos`) y queda como
    # `Archivo`, no como texto sin validar.
    evidencia_archivo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("archivo.id"), nullable=True
    )
    # Los tres siguientes solo se llenan al completar con resultado
    # `conforme`: son lo que el listener de `inventory` necesita para que el
    # lote del producto terminado nazca con vencimiento real (RN-VNC-001) y
    # no como FIFO por defecto. `fecha_vencimiento`/`lote_codigo` viajan
    # también en el payload de `production.orden_completada`.
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    lote_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Trazabilidad fina de fabricación (RN-LOT-002/003): manipulador_id,
    # envasador_id, linea, variables_proceso — la forma la define quien
    # complete la orden, no hay un esquema fijo todavía (QR queda pendiente).
    trazabilidad: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # Nullable desde `feat/produccion-orden-por-necesidad`: una orden
    # `ajuste_por_necesidad` la crea el listener, sin ningún humano detrás
    # (RN-PRD-007) — igual criterio que `usuario_id` nulo en
    # `inventory.stock_bajo_minimo`, que el reporte muestra como «Sistema».
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    # Nullable y únicas: sin clave, un reintento de red puede duplicar el
    # consumo o completar la orden dos veces (deuda técnica, ver ROADMAP).
    consumo_idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    cierre_idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
