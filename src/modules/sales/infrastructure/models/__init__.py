"""Modelos del módulo sales — núcleo del slice Venta + Cobro (data-model
§3, §6).

Alcance: `venta`/`venta_item` (PROC-COM-001), `cliente`, `punto_venta`,
`producto_comercial`, `medio_pago`/`pago` (PROC-COM-002 — cobro).
`comprobante` vive en `shared` (transversal a sales/purchases/accounting).
Precio server-side: `lista_precio` + `precio` (RN-PRC-003).
Variantes: `producto_comercial.producto_padre_id` (tamaños con receta y
precio propios) + `producto_opcion_grupo` (qué grupos de extras son
obligatorios). Cupón de promoción: `promocion_cupon` + `cupon` (ADR-061).
Diferido a un slice posterior: combo, la `promocion` ligada a lista de
precios de §6, carrito, central_pedidos, cuenta_puntos, carta_disputa_pago.
"""

from src.modules.sales.infrastructure.models.alerta_pedido import AlertaPedido
from src.modules.sales.infrastructure.models.atributo import Atributo
from src.modules.sales.infrastructure.models.atributo_valor import AtributoValor
from src.modules.sales.infrastructure.models.cliente import Cliente
from src.modules.sales.infrastructure.models.cupon import Cupon
from src.modules.sales.infrastructure.models.kds_pantalla import KdsPantalla
from src.modules.sales.infrastructure.models.lista_precio import ListaPrecio
from src.modules.sales.infrastructure.models.medio_pago import MedioPago
from src.modules.sales.infrastructure.models.mesa import Mesa
from src.modules.sales.infrastructure.models.pago import Pago
from src.modules.sales.infrastructure.models.pedido_borrador import PedidoBorrador
from src.modules.sales.infrastructure.models.precio import Precio
from src.modules.sales.infrastructure.models.producto_atributo_linea import (
    ProductoAtributoLinea,
)
from src.modules.sales.infrastructure.models.producto_atributo_valor import (
    ProductoAtributoValor,
)
from src.modules.sales.infrastructure.models.producto_comercial import (
    ProductoComercial,
)
from src.modules.sales.infrastructure.models.producto_comercial_extra import (
    ProductoComercialExtra,
)
from src.modules.sales.infrastructure.models.producto_exclusion import (
    ProductoExclusion,
)
from src.modules.sales.infrastructure.models.producto_opcion_grupo import (
    ProductoOpcionGrupo,
)
from src.modules.sales.infrastructure.models.producto_variante_valor import (
    ProductoVarianteValor,
)
from src.modules.sales.infrastructure.models.promocion_cupon import PromocionCupon
from src.modules.sales.infrastructure.models.punto_venta import PuntoVenta
from src.modules.sales.infrastructure.models.venta import Venta
from src.modules.sales.infrastructure.models.venta_item import VentaItem

__all__ = [
    "AlertaPedido",
    "Atributo",
    "AtributoValor",
    "Cliente",
    "Cupon",
    "KdsPantalla",
    "ListaPrecio",
    "MedioPago",
    "Mesa",
    "Pago",
    "PedidoBorrador",
    "Precio",
    "ProductoAtributoLinea",
    "ProductoAtributoValor",
    "ProductoComercial",
    "ProductoComercialExtra",
    "ProductoExclusion",
    "ProductoOpcionGrupo",
    "ProductoVarianteValor",
    "PromocionCupon",
    "PuntoVenta",
    "Venta",
    "VentaItem",
]
