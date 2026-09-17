"""Carrito del sitio de marca: reglas puras, sin infraestructura.

El precio nunca se calcula acá — lo fija `sales` server-side al confirmar
(RN-PRC-003, `crear_venta`), igual que cualquier otro canal. Esto solo
valida la FORMA del carrito antes de mandarlo.

Simplificación deliberada de PR3 (ADR-103): una línea es "un producto
comercial (ya sea la pizza o el tamaño/variante elegido) + una cantidad".
Extras (máx. 3) y Mitad x Mitad de la carta de Charlie's (brand guideline
§3.1.8) todavía no tienen un concepto en `sales` del que colgarse — ni
catálogo de extras ni combos —, así que quedan fuera de este slice. Ver
`docs/roadmap/deuda/modulo-storefront.md`.
"""

import uuid
from dataclasses import dataclass

CANTIDAD_MAXIMA_POR_LINEA = 20
LINEAS_MAXIMAS_POR_PEDIDO = 30


@dataclass(frozen=True)
class LineaCarrito:
    producto_comercial_id: uuid.UUID
    cantidad: int


def validar(lineas: list[LineaCarrito]) -> None:
    if not lineas:
        raise ValueError("el carrito está vacío")
    if len(lineas) > LINEAS_MAXIMAS_POR_PEDIDO:
        raise ValueError(f"máximo {LINEAS_MAXIMAS_POR_PEDIDO} líneas por pedido")
    for linea in lineas:
        if linea.cantidad <= 0:
            raise ValueError("la cantidad debe ser mayor a cero")
        if linea.cantidad > CANTIDAD_MAXIMA_POR_LINEA:
            raise ValueError(f"cantidad máxima por producto: {CANTIDAD_MAXIMA_POR_LINEA}")
