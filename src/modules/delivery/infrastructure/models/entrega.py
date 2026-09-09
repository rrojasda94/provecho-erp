"""Entrega: una por venta (RN-CUP-005), con su historial de intentos,
resultado y evidencia (ADR-098). Ejecuta la rama delivery de
`PROC-OPE-002` que `sales.application.cumplimiento` no cubre.

`venta_id` referencia `venta.id` por nombre de tabla, no por import: es
FK de base de datos (integridad referencial), nunca un import del dominio
de `sales` — mismo patrón que `marketing.encuesta_satisfaccion.venta_id`.

`entregado_por` guarda el `usuario_id` del **repartidor** que entregó
(RN-CUP-007), no necesariamente quien tocó el botón — un despachador puede
registrar la entrega en nombre del repartidor cuyo celular se quedó sin
batería; quién la registró de verdad queda en `audit_log`.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin
from src.modules.delivery.domain import rules


class Entrega(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "entrega"

    __table_args__ = (
        Index("ix_entrega_sucursal_estado", "sucursal_id", "estado"),
        Index("ix_entrega_ruta_orden", "ruta_id", "orden_parada"),
        UniqueConstraint("venta_id", name="uq_entrega_venta"),
        CheckConstraint(
            "estado IN ({})".format(", ".join(f"'{v}'" for v in rules.ESTADOS_ENTREGA)),
            name="estado_entrega",
        ),
        CheckConstraint(
            "motivo_fallo IS NULL OR motivo_fallo IN ({})".format(
                ", ".join(f"'{v}'" for v in rules.MOTIVOS_FALLO)
            ),
            name="motivo_fallo_entrega",
        ),
    )

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"))
    # Denormalizado de la venta al asignar: escopa por tenant (sucursal) sin
    # que `delivery` tenga que leer `venta.sucursal_id` en cada consulta del
    # tablero — la lee una vez, al crear la ruta, vía `queries_publicas`.
    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    ruta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ruta_reparto.id"), nullable=True)
    repartidor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repartidor.id"), nullable=True
    )
    # Posición de esta parada dentro de la ruta (0-based). NULL fuera de una
    # ruta — `pendiente` no tiene todavía un lugar en ninguna.
    orden_parada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(*rules.ESTADOS_ENTREGA, name="estado_entrega", native_enum=False),
        default="pendiente",
    )
    # RN-DLV-004: el reintento reutiliza esta misma fila y sube el contador
    # — el intento anterior queda en `audit_log`, no en una tabla propia.
    intentos: Mapped[int] = mapped_column(Integer, default=1)
    eta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tramo_distancia_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tramo_duracion_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Copia de la ubicación de la venta al asignar (no se relee si el
    # cliente corrige su dirección después: esta parada ya se calculó).
    destino_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    destino_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entregado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    motivo_fallo: Mapped[str | None] = mapped_column(
        Enum(*rules.MOTIVOS_FALLO, name="motivo_fallo_entrega", native_enum=False),
        nullable=True,
    )
    # Obligatorio si motivo_fallo="otro" (RN-DLV-003) — validado en el
    # dominio/aplicación, no en el esquema de la base.
    motivo_detalle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resultado_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    resultado_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    # Foto de evidencia, mismo tratamiento que `rrhh.marcacion.foto`: sin
    # ruta de subida a S3 real en el proyecto todavía (deuda declarada,
    # `docs/roadmap/deuda/modulo-delivery.md`). `deferred`: no viaja en
    # cada SELECT de la fila, solo cuando se pide explícitamente.
    evidencia_foto: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    observacion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Credencial anónima del enlace público (RN-DLV-008). Único: dos
    # entregas nunca comparten token, ni siquiera por reintento — cada
    # asignación a ruta lo regenera.
    token_publico: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    token_expira_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aviso_en_camino_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    aviso_resultado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    aviso_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
