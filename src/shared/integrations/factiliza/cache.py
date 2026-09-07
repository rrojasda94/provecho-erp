"""Caché de consulta de documento (DNI/RUC), con TTL.

`consultar_dni`/`consultar_ruc` se pagan por llamada a un proveedor externo,
y hoy se llaman **dos veces** por cada alta: el botón «Buscar» del
formulario consulta una vez, y al guardar `nombres_desde_dni`/
`razon_social_desde_ruc` vuelven a consultar el mismo documento para no
confiar en lo que llegó del cliente (ADR-041). La segunda llamada es
deliberada y no se quita — pero no tiene por qué volver a pagarle al
proveedor si la primera ya trajo la respuesta hace unos segundos.

**Con TTL, y por eso no se copia** `sales.tarifa_delivery._distancia_cacheada`
**(`lru_cache` sin vencer)**: la distancia entre dos puntos fijos no cambia
nunca; un documento sí (cambio de nombre, RUC dado de baja), así que
guardarlo para siempre mostraría un dato viejo sin límite. Redis y no
`lru_cache` con TTL manual: el vencimiento vive del lado del servidor de
caché, no hay que reinventarlo con una segunda estructura en memoria.

Solo se cachea una respuesta que **llegó** — un fallo del proveedor
(`FactilizaError`) nunca se guarda, para que el siguiente intento vuelva a
salir a la red en vez de repetir el mismo error durante todo el TTL. Falla
en silencio, igual que `core/rate_limit.py`: un Redis caído no debe impedir
la consulta, solo perder la caché.
"""

import json

import redis

from src.config.settings import settings

_TIMEOUT_SEGUNDOS = 0.2
_client = redis.from_url(
    settings.redis_url,
    socket_timeout=_TIMEOUT_SEGUNDOS,
    socket_connect_timeout=_TIMEOUT_SEGUNDOS,
)

# Alcanza para las dos consultas del alta (botón «Buscar» + revalidación al
# guardar) sin quedar tan vieja como para mostrar un RUC ya dado de baja.
TTL_SEGUNDOS = 300


def _clave(tipo: str, numero: str) -> str:
    return f"consulta:{tipo}:{numero}"


def obtener(tipo: str, numero: str) -> dict | None:
    """El dict guardado para `(tipo, numero)`, o `None` si no está — sin
    distinguir "no cacheado" de "Redis no responde": las dos veces toca
    salir a consultar de nuevo."""
    try:
        crudo = _client.get(_clave(tipo, numero))
    except redis.RedisError:
        return None
    if crudo is None:
        return None
    return json.loads(crudo)


def guardar(tipo: str, numero: str, datos: dict) -> None:
    try:
        _client.set(
            _clave(tipo, numero), json.dumps(datos, default=str), ex=TTL_SEGUNDOS
        )
    except redis.RedisError:
        pass
