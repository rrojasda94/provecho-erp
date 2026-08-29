"""Asiento contable: cabecera. `origen` distingue manual (permiso
`accounting.asiento_manual`) de automático (generado por un evento operativo
vía `regla_asiento`, RN-CTB-003)."""

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Asiento(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "asiento"
    __table_args__ = (
        # `vw_bi_contabilidad` (ADR-081) agrupa por empresa y rango de fecha.
        Index("ix_asiento_fecha_empresa", "fecha", "empresa_id"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    periodo_contable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("periodo_contable.id"))
    fecha: Mapped[date] = mapped_column(Date)
    glosa: Mapped[str] = mapped_column(String(255))
    origen: Mapped[str] = mapped_column(
        Enum("manual", "automatico", name="origen_asiento", native_enum=False)
    )
    # Nombre del evento que lo generó (ej. "purchases.oc_emitida"), NULL si manual.
    evento_origen: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Id de la entidad de origen (venta_id, orden_compra_id...), NULL si manual.
    referencia_origen: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum("registrado", "anulado", name="estado_asiento", native_enum=False),
        default="registrado",
    )
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    # RN-CTB-002: anular = crear asiento inverso, nunca borrar/editar el original.
    asiento_reversa_de_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("asiento.id"), nullable=True
    )
