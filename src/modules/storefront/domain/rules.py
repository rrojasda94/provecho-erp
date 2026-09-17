"""Reglas puras del sitio de marca: sin FastAPI, SQLAlchemy ni red.

`CLAVES_CONTENIDO` es el vocabulario cerrado del CMS mínimo
(`storefront_contenido.clave`) — agregar una clave nueva es una decisión de
producto, no algo que un `PUT` cualquiera pueda inventar.
"""

import datetime

CLAVES_CONTENIDO = ("hero", "nosotros", "contacto", "trabaja", "pie", "seo")

# Lockout de clave de cuenta (ADR-102) — mismos valores que `users`
# (`MAX_INTENTOS_FALLIDOS`/`DURACION_BLOQUEO`): no hay razón para que una
# cuenta de cliente tolere más intentos de fuerza bruta que una de staff.
MAX_INTENTOS_FALLIDOS = 5
DURACION_BLOQUEO = datetime.timedelta(minutes=15)

ENTIDADES_FOTO = {
    "producto": "producto_comercial_foto",
    "ingrediente": "articulo_foto",
}

MIME_FOTO = ("image/jpeg", "image/png", "image/webp")
TAMANO_MAXIMO_FOTO_BYTES = 5 * 1024 * 1024

DIAS_SEMANA = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")

# `date.weekday()`: 0 = lunes.
_DIA_POR_INDICE = DIAS_SEMANA


def abierto_ahora(horario: dict | None, ahora: datetime.datetime) -> bool | None:
    """¿El local está abierto en este instante, según `horario_atencion`?

    `None` cuando el horario no existe o no tiene la forma esperada
    (`{"lun": [["HH:MM","HH:MM"]], ...}`) — filas heredadas del JSONB libre
    que precedía a este esquema (ADR-101). El sitio muestra "consultar
    horario" en ese caso, nunca un booleano adivinado.
    """
    if not isinstance(horario, dict):
        return None
    clave = _DIA_POR_INDICE[ahora.weekday()]
    tramos = horario.get(clave)
    if tramos is None:
        return None
    if not isinstance(tramos, list):
        return None
    hora_actual = ahora.time()
    for tramo in tramos:
        try:
            desde_str, hasta_str = tramo
            desde = datetime.time.fromisoformat(desde_str)
            hasta = datetime.time.fromisoformat(hasta_str)
        except (ValueError, TypeError):
            return None
        if desde <= hora_actual <= hasta:
            return True
    return False
