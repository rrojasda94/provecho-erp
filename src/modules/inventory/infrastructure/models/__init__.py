"""Modelos del módulo inventory — bloque transversal + base de productos
(data-model §1, §3). Stock/movimientos/transferencias/lote se modelan en
el slice dedicado de Inventario.
"""

from src.modules.inventory.infrastructure.models.articulo import Articulo
from src.modules.inventory.infrastructure.models.categoria import Categoria
from src.modules.inventory.infrastructure.models.categoria_udm import CategoriaUdm
from src.modules.inventory.infrastructure.models.receta import Receta
from src.modules.inventory.infrastructure.models.receta_item import RecetaItem
from src.modules.inventory.infrastructure.models.sku import Sku
from src.modules.inventory.infrastructure.models.unidad_medida import UnidadMedida

__all__ = [
    "Articulo",
    "Categoria",
    "CategoriaUdm",
    "Receta",
    "RecetaItem",
    "Sku",
    "UnidadMedida",
]
