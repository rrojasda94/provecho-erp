"""Modelos del módulo inventory — bloque transversal, base de productos,
stock/movimientos/ajuste y lote/FEFO (data-model §1, §3, §4). Transferencias,
reservas, conteo y devolución se modelan en slices posteriores.
"""

from src.modules.inventory.infrastructure.models.ajuste import Ajuste
from src.modules.inventory.infrastructure.models.articulo import Articulo
from src.modules.inventory.infrastructure.models.categoria import Categoria
from src.modules.inventory.infrastructure.models.categoria_udm import CategoriaUdm
from src.modules.inventory.infrastructure.models.lote import Lote
from src.modules.inventory.infrastructure.models.movimiento_inventario import (
    MovimientoInventario,
)
from src.modules.inventory.infrastructure.models.receta import Receta
from src.modules.inventory.infrastructure.models.receta_item import RecetaItem
from src.modules.inventory.infrastructure.models.sku import Sku
from src.modules.inventory.infrastructure.models.stock import Stock
from src.modules.inventory.infrastructure.models.stock_lote import StockLote
from src.modules.inventory.infrastructure.models.unidad_medida import UnidadMedida

__all__ = [
    "Ajuste",
    "Articulo",
    "Categoria",
    "CategoriaUdm",
    "Lote",
    "MovimientoInventario",
    "Receta",
    "RecetaItem",
    "Sku",
    "Stock",
    "StockLote",
    "UnidadMedida",
]
