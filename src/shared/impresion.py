"""Formato del papel térmico de 80 mm.

Todas las ticketeras del grupo son de 80 mm, así que el ancho es **uno solo**
y vive acá: la comanda de cocina, la precuenta y el ticket del comprobante lo
comparten (ADR-066). Cuando cada documento traía el suyo —32 columnas la
comanda, 40 la precuenta— el mismo rollo salía con tres márgenes distintos y
la comanda desperdiciaba un tercio del papel.

48 columnas es lo que entra en 80 mm con la fuente A (12x24) de ESC/POS, y es
también lo que rinde el CSS de `frontend/components/impresion`: el texto que
sale de acá y el HTML que se manda a la impresora tienen que cortar en la
misma columna, o el mismo documento se lee distinto según por dónde salga.

Sin lógica de negocio: son cortes de texto. Lo que dice cada documento lo
decide su módulo.
"""

import textwrap
from decimal import Decimal

# Columnas útiles de un rollo de 80 mm en fuente A.
ANCHO = 48


def regla(caracter: str = "=") -> str:
    return caracter * ANCHO


def centrar(texto: str) -> str:
    return texto.center(ANCHO)


def izq_der(izquierda: str, derecha: str) -> str:
    """Etiqueta a la izquierda, valor pegado al borde derecho.

    Si no entran los dos, gana el de la derecha: es el monto, y un total
    truncado es peor que un nombre truncado.
    """
    espacio = ANCHO - len(derecha)
    if espacio <= 0:
        return derecha[-ANCHO:]
    return f"{izquierda[:espacio]:<{espacio}}{derecha}"


def monto(etiqueta: str, valor: Decimal, moneda: str = "S/") -> str:
    return izq_der(etiqueta, f"{moneda} {valor:.2f}")


def envolver(texto: str, sangria: str = "") -> list[str]:
    """Parte un texto largo en líneas que caben en el rollo."""
    return textwrap.wrap(texto, ANCHO - len(sangria), subsequent_indent=sangria) or [""]
