"""Modelos del módulo production: orden de producción y su consumo real
(data-model.md §7)."""

from src.modules.production.infrastructure.models.consumo_produccion_item import (
    ConsumoProduccionItem,
)
from src.modules.production.infrastructure.models.orden_produccion import OrdenProduccion

__all__ = ["ConsumoProduccionItem", "OrdenProduccion"]
