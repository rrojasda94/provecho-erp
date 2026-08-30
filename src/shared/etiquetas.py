"""Nombre humano de un campo de la API, para los mensajes de error.

Un 422 que dice `unidad_medida_id` obliga a adivinar a qué control de la
pantalla se refiere. Quitar el sufijo `_id` y cambiar `_` por espacio
alcanza para casi todo el catálogo de campos del ERP; lo que esa regla
arruina son dos cosas concretas: las palabras pierden la tilde
("Almacen", "Codigo") y las siglas quedan capitalizadas ("Ruc", "Igv").

Por eso el diccionario es **por palabra** y no por campo: `codigo`,
`codigo_barras` y `numero_orden` se corrigen con tres entradas y no con
una por cada campo de cada schema — que es lo que se desincroniza. Los
pocos nombres que ni así se leen (`page_size`, `merma_pct`) van en
`ETIQUETAS`, que gana sobre todo lo demás.

Esto no es i18n: la API habla español y no hay un segundo idioma que
soportar. El día que lo haya, este archivo es el único que se toca.
"""

import re

# Campo completo → etiqueta. Solo para lo que la regla general no puede
# deducir: abreviaturas, nombres técnicos y campos que se leen al revés.
ETIQUETAS: dict[str, str] = {
    "page": "Página",
    "page_size": "Tamaño de página",
    "idempotency_key": "Clave de idempotencia",
    "username": "Usuario",
    "merma_pct": "Merma (%)",
    "id_interno": "Identificador interno",
    "ubicacion_lat": "Latitud",
    "ubicacion_lng": "Longitud",
    "ubicacion_place_id": "Lugar de Google",
    "ubicacion_plus_code": "Plus Code",
    "unidad_medida_id": "Unidad de medida",
    "rendimiento_unidad_medida_id": "Unidad de medida del rendimiento",
    "fecha_emision": "Fecha de emisión",
    "fecha_vencimiento": "Fecha de vencimiento",
    "numero_documento": "Número de documento",
    "tipo_documento": "Tipo de documento",
    "punto_venta_id": "Punto de venta",
    "desde": "Fecha desde",
    "hasta": "Fecha hasta",
    "q": "Búsqueda",
}

# Palabra → forma correcta. La clave se escribe como aparece en el campo
# (sin tilde, en minúscula); el valor es lo que se muestra.
PALABRAS: dict[str, str] = {
    # Siglas: van enteras en mayúscula.
    "ruc": "RUC",
    "dni": "DNI",
    "igv": "IGV",
    "isc": "ISC",
    "sku": "SKU",
    "pin": "PIN",
    "pdf": "PDF",
    "xml": "XML",
    "cdr": "CDR",
    "url": "URL",
    "pos": "POS",
    "kds": "KDS",
    "pdv": "PDV",
    "pct": "%",
    # Tildes que la limpieza automática se come. Las terminadas en -ción y
    # -sión no están: las cubre `_SUFIJOS`.
    "almacen": "almacén",
    "articulo": "artículo",
    "campana": "campaña",
    "categoria": "categoría",
    "codigo": "código",
    "credito": "crédito",
    "dias": "días",
    "linea": "línea",
    "maximo": "máximo",
    "metodo": "método",
    "minimo": "mínimo",
    "modulo": "módulo",
    "numero": "número",
    "periodo": "período",
    "razon": "razón",
    "telefono": "teléfono",
}

# En español ninguna palabra termina en `-cion` o `-sion` sin tilde, así que
# la regla vale para todas y ahorra un renglón por cada `observacion`,
# `autorizacion`, `devolucion`... que aparezca en un schema nuevo. El plural
# (`observaciones`) sí va sin tilde y por eso no entra acá.
_SUFIJOS = (("cion", "ción"), ("sion", "sión"))

# `items[0].cantidad` → la etiqueta la manda `cantidad`: el índice y el
# camino ya viajan en `campo`, repetirlos en la etiqueta no aclara nada.
_INDICE = re.compile(r"\[\d+\]")


def etiqueta(campo: str) -> str:
    """Nombre legible de `campo`, tal como se le muestra a quien carga el dato."""
    clave = _INDICE.sub("", campo).rsplit(".", 1)[-1]
    if clave in ETIQUETAS:
        return ETIQUETAS[clave]
    palabras = [_palabra(p) for p in clave.removesuffix("_id").split("_") if p]
    if not palabras:
        return campo
    texto = " ".join(palabras)
    return texto[0].upper() + texto[1:]


def _palabra(palabra: str) -> str:
    if palabra in PALABRAS:
        return PALABRAS[palabra]
    for sufijo, acentuado in _SUFIJOS:
        if palabra.endswith(sufijo):
            return palabra[: -len(sufijo)] + acentuado
    return palabra
