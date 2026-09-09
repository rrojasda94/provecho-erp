"""Detalle de insumos realmente consumidos por una orden — contrastado
contra `receta_item.merma_pct` (esperado) para medir desperdicio real."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import UuidPkMixin


class ConsumoProduccionItem(Base, UuidPkMixin):
    __tablename__ = "consumo_produccion_item"

    orden_produccion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden_produccion.id"))
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    # NULL = la del artículo (mismo criterio que `receta_item.unidad_medida_id`).
    # Cuando quien registra el consumo tecleó en otra UdM de la misma
    # categoría (RN-UDM-005) — gramos sobre un insumo que se lleva en
    # kilos — `cantidad` ya viaja convertida a la unidad del artículo: es
    # la que `costo_insumos`/`desviacion_desperdicio` necesitan para cuadrar
    # con lo que la receta espera. Esta columna solo deja constancia de en
    # qué unidad se tecleó, para auditoría — no participa en ningún cálculo.
    unidad_medida_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("unidad_medida.id"), nullable=True
    )
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    peso_desperdicio_real: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(0))
    tipo_desperdicio: Mapped[str | None] = mapped_column(String(50), nullable=True)
