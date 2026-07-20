"""Modelos del módulo sales — núcleo del slice Venta (data-model §3, §6).

Alcance de este slice: `venta`/`venta_item` (PROC-COM-001, hasta envío a
cocina + cobro, RN-COM-005), `cliente`, `punto_venta`, `producto_comercial`
base. Diferido a un slice posterior: modificador/variante_producto/combo,
lista_precio/precio/promocion, medio_pago/pago/comprobante (PROC-COM-002),
carrito, central_pedidos, cuenta_puntos.
"""

from src.modules.sales.infrastructure.models.cliente import Cliente
from src.modules.sales.infrastructure.models.producto_comercial import (
    ProductoComercial,
)
from src.modules.sales.infrastructure.models.punto_venta import PuntoVenta
from src.modules.sales.infrastructure.models.venta import Venta
from src.modules.sales.infrastructure.models.venta_item import VentaItem

__all__ = ["Cliente", "ProductoComercial", "PuntoVenta", "Venta", "VentaItem"]
