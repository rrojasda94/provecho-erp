"""Cierre de caja (PROC-CTB-001 v1.1). Irregularidades notifican a
contabilidad, gerencia y RRHH (evento `accounting.cierre_caja_irregular`).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class CierreCaja(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "cierre_caja"
    __table_args__ = (UniqueConstraint("apertura_caja_id"),)

    # 1:1 — un cierre por apertura.
    apertura_caja_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apertura_caja.id"))
    cajero_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    montos_esperados: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    montos_reales: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    descuadre_monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    # Según en qué etapa se detecta y documenta (RN-MDP-005).
    descuadre_atribucion: Mapped[str | None] = mapped_column(
        Enum(
            "cajero",
            "tercero_reportado",
            "encargado",
            name="descuadre_atribucion",
            native_enum=False,
        ),
        nullable=True,
    )
    # Referencias a `archivo` (reportes de cierre de lote de cada POS).
    reportes_pos: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Quién actuó sobre este cierre y cuándo — lista de
    # {rol, usuario_id, timestamp}. Desde ADR-049 son actos del cajero (el
    # cierre y cada recuento tras una reapertura): la entrega del efectivo
    # dejó de anotarse acá porque ya no ocurre al cerrar, y su rastro vive
    # en `custodia_efectivo.timestamps_relevo`, que es donde la firma existe.
    relevos: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Reaperturas y recuentos: un cierre con faltante se corrige, y la
    # corrección tiene que verse. Lista de {motivo, autorizado_por,
    # descuadre_anterior, timestamp} — un registro por reapertura
    # (RN-MDP-005).
    correcciones: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    custodia: Mapped[str] = mapped_column(
        Enum(
            "local_caja_fuerte",
            "traslado_contabilidad",
            name="custodia_cierre_caja",
            native_enum=False,
        )
    )
    estado: Mapped[str] = mapped_column(
        Enum(
            "en_proceso",
            "conforme",
            "con_irregularidad",
            name="estado_cierre_caja",
            native_enum=False,
        ),
        default="en_proceso",
    )
