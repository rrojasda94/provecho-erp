"""Artículo: cualquier ítem inventariable que vive en un almacén."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
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
    # Con cuánta anticipación este artículo se considera "por vencer". Va acá
    # y no en un número global porque la ventana útil depende del artículo:
    # la leche avisa con 3 días y una conserva con 60, y un solo número deja
    # a uno de los dos avisando tarde. NULL = sin ventana; la consulta puede
    # imponer la suya.
    dias_alerta_vencimiento: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # Identificador del sistema de origen ("__export__.product_template_1308_...").
    # `id_interno` son 4 caracteres que la gente teclea; esto es la clave del
    # otro sistema, que puede tener cualquier forma. Reimportar la misma
    # planilla actualiza en vez de duplicar (ADR-057).
    ref_externa: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True
    )
