"""Modelos del módulo sales — núcleo del slice Venta + Cobro (data-model
§3, §6).

Alcance: `venta`/`venta_item` (PROC-COM-001), `cliente`, `punto_venta`,
`producto_comercial`, `medio_pago`/`pago` (PROC-COM-002 — cobro).
`comprobante` vive en `shared` (transversal a sales/purchases/accounting).
Precio server-side: `lista_precio` + `precio` (RN-PRC-003).
Diferido a un slice posterior: modificador/variante_producto/combo,
`promocion`, carrito, central_pedidos, cuenta_puntos, carta_disputa_pago.
"""

from src.modules.sales.infrastructure.models.cliente import Cliente
from src.modules.sales.infrastructure.models.kds_pantalla import KdsPantalla
from src.modules.sales.infrastructure.models.lista_precio import ListaPrecio
from src.modules.sales.infrastructure.models.medio_pago import MedioPago
from src.modules.sales.infrastructure.models.pago import Pago
from src.modules.sales.infrastructure.models.precio import Precio
from src.modules.sales.infrastructure.models.producto_comercial import (
    ProductoComercial,
)
from src.modules.sales.infrastructure.models.punto_venta import PuntoVenta
from src.modules.sales.infrastructure.models.venta import Venta
from src.modules.sales.infrastructure.models.venta_item import VentaItem

__all__ = [
    "Cliente",
    "KdsPantalla",
    "ListaPrecio",
    "MedioPago",
    "Pago",
    "Precio",
    "ProductoComercial",
    "PuntoVenta",
    "Venta",
    "VentaItem",
]
