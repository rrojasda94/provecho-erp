"""Formato título en español para los nombres que teclea el usuario.

Un mismo insumo escrito "queso mozzarella", "Queso Mozzarella" y "QUESO
MOZZARELLA" son tres nombres distintos para el buscador y tres filas
distintas en un reporte. Normalizar al terminar de escribir evita el
duplicado, no lo corrige después.

La regla es la del español, no la del inglés: los conectores van en
minúscula salvo que abran el nombre —"Pizza de Peperoni Familiar", no
"Pizza De Peperoni Familiar"—. Las siglas cortas en mayúscula se respetan
("Pizza XL" no se convierte en "Pizza Xl").

El frontend aplica lo mismo al salir del campo (`frontend/lib/texto.ts`);
acá se normaliza igual porque la API tiene más clientes que esa pantalla
—kiosko, hub, seeders— y el formato no puede depender de quién escribe.
"""

import re

# Preposiciones, artículos y conjunciones que van en minúscula dentro del
# nombre. En primera posición siempre suben a mayúscula.
CONECTORES = frozenset(
    {
        "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "e",
        "el", "en", "entre", "hacia", "hasta", "la", "las", "los", "o", "para",
        "por", "según", "sin", "sobre", "tras", "u", "y",
    }
)

# Separadores que también abren palabra: "coca-cola" → "Coca-Cola".
_SEPARADORES = re.compile(r"([\-/])")


def a_titulo(texto: str | None) -> str | None:
    """Devuelve `texto` en formato título español, con espacios colapsados.

    `None` y la cadena vacía pasan tal cual: normalizar no es completar.
    """
    if texto is None:
        return None
    palabras = texto.split()
    if not palabras:
        return ""
    return " ".join(
        _palabra(p, primera=(i == 0)) for i, p in enumerate(palabras)
    )


def _palabra(palabra: str, *, primera: bool) -> str:
    partes = _SEPARADORES.split(palabra)
    # Solo la primera parte de un compuesto puede ser conector inicial:
    # en "de-la" la segunda parte ya no abre el nombre.
    return "".join(
        parte if _SEPARADORES.fullmatch(parte) else _parte(parte, primera and i == 0)
        for i, parte in enumerate(partes)
    )


def _parte(parte: str, primera: bool) -> str:
    if not parte:
        return parte
    # Sigla ya escrita en mayúscula (XL, IGV, CH1): el usuario la escribió
    # así a propósito y capitalizarla la arruinaría.
    if len(parte) <= 4 and parte.isupper():
        return parte
    if not primera and parte.lower() in CONECTORES:
        return parte.lower()
    return parte[0].upper() + parte[1:].lower()
