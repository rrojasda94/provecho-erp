"""Modelos del módulo inventory — bloque transversal, base de productos,
stock/movimientos/ajuste, lote/FEFO, conteo cíclico y el ciclo
solicitud → reserva → transferencia → recepción con su guía de remisión
(data-model §1, §3, §4). `devolucion` y `stock_merma` van en slices
posteriores.
"""

from src.modules.inventory.infrastructure.models.ajuste import Ajuste
from src.modules.inventory.infrastructure.models.articulo import Articulo
from src.modules.inventory.infrastructure.models.categoria import Categoria
from src.modules.inventory.infrastructure.models.categoria_udm import CategoriaUdm
from src.modules.inventory.infrastructure.models.conteo import Conteo
from src.modules.inventory.infrastructure.models.conteo_item import ConteoItem
from src.modules.inventory.infrastructure.models.devolucion import Devolucion
from src.modules.inventory.infrastructure.models.devolucion_item import DevolucionItem
from src.modules.inventory.infrastructure.models.guia_remision import GuiaRemision
from src.modules.inventory.infrastructure.models.guia_remision_item import (
    GuiaRemisionItem,
)
from src.modules.inventory.infrastructure.models.incidencia_inventario import (
    IncidenciaInventario,
)
from src.modules.inventory.infrastructure.models.lote import Lote
from src.modules.inventory.infrastructure.models.movimiento_inventario import (
    MovimientoInventario,
)
from src.modules.inventory.infrastructure.models.receta import Receta
from src.modules.inventory.infrastructure.models.receta_item import RecetaItem
from src.modules.inventory.infrastructure.models.reserva_stock import ReservaStock
from src.modules.inventory.infrastructure.models.sku import Sku
from src.modules.inventory.infrastructure.models.solicitud_insumos import (
    SolicitudInsumos,
)
from src.modules.inventory.infrastructure.models.solicitud_item import SolicitudItem
from src.modules.inventory.infrastructure.models.stock import Stock
from src.modules.inventory.infrastructure.models.stock_lote import StockLote
from src.modules.inventory.infrastructure.models.transferencia import Transferencia
from src.modules.inventory.infrastructure.models.transferencia_item import (
    TransferenciaItem,
)
from src.modules.inventory.infrastructure.models.unidad_medida import UnidadMedida

__all__ = [
    "Ajuste",
    "Articulo",
    "Categoria",
    "CategoriaUdm",
    "Conteo",
    "ConteoItem",
    "Devolucion",
    "DevolucionItem",
    "GuiaRemision",
    "GuiaRemisionItem",
    "IncidenciaInventario",
    "Lote",
    "MovimientoInventario",
    "Receta",
    "RecetaItem",
    "ReservaStock",
    "Sku",
    "SolicitudInsumos",
    "SolicitudItem",
    "Stock",
    "StockLote",
    "Transferencia",
    "TransferenciaItem",
    "UnidadMedida",
]
