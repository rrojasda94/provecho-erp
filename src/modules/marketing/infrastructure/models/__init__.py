"""Modelos del módulo marketing (data-model.md §8d)."""

from src.modules.marketing.infrastructure.models.campana import Campana
from src.modules.marketing.infrastructure.models.encuesta_satisfaccion import (
    EncuestaSatisfaccion,
)
from src.modules.marketing.infrastructure.models.implementacion_material_sucursal import (
    ImplementacionMaterialSucursal,
)
from src.modules.marketing.infrastructure.models.lead import Lead
from src.modules.marketing.infrastructure.models.pieza_contenido import PiezaContenido

__all__ = [
    "Campana",
    "EncuestaSatisfaccion",
    "ImplementacionMaterialSucursal",
    "Lead",
    "PiezaContenido",
]
