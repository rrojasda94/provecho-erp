"""Carrito del sitio de marca: reglas puras, sin infraestructura.

El precio nunca se calcula acá — lo fija `sales` server-side al confirmar
(RN-PRC-003, `crear_venta`), igual que cualquier otro canal. Esto solo
valida la FORMA del carrito antes de mandarlo.

Una línea es "un producto comercial (la pizza o el tamaño/variante elegido) +
una cantidad + lo que se le eligió": extras y sabores (Mitad x Mitad), los
mismos que ya modela `sales` para el PDV. Validarlos contra lo que el producto
ofrece es de `domain/opciones.py`.
"""

import uuid
from dataclasses import dataclass

CANTIDAD_MAXIMA_POR_LINEA = 20
LINEAS_MAXIMAS_POR_PEDIDO = 30


@dataclass(frozen=True)
class LineaCarrito:
    producto_comercial_id: uuid.UUID
    cantidad: int
    # `(extra_id, cantidad por unidad)`, en el orden en que se eligieron.
    extras: tuple[tuple[uuid.UUID, int], ...] = ()
    # `producto_atributo_valor.id` elegidos (los sabores de la Mitad x Mitad).
    valores: tuple[uuid.UUID, ...] = ()


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
