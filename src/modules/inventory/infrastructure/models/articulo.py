"""Artículo: cualquier ítem inventariable que vive en un almacén."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Articulo(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "articulo"
    __table_args__ = (UniqueConstraint("id_interno"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    id_interno: Mapped[str] = mapped_column(String(4))
    nombre: Mapped[str] = mapped_column(String(150))
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categoria.id"), nullable=True
    )
    unidad_medida_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidad_medida.id"))
    # Enum extensible (insumo, subreceta, mercaderia, empaque, repuesto,
    # suministro, ...) — String a propósito, se agregan tipos sin migración
    # destructiva.
    tipo: Mapped[str] = mapped_column(String(30))
    costo_promedio: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    archivado: Mapped[bool] = mapped_column(Boolean, default=False)
    # Solo los artículos que lo declaran mueven stock por lote y respetan
    # FEFO (ADR-015). Perecibles y trazables sí; servilletas no.
    controla_lote: Mapped[bool] = mapped_column(Boolean, default=False)
