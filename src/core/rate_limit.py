"""Guardas con estado efímero en Redis: contador de ventana fija y marca de
un solo uso.

El lockout de `usuario` (5 intentos) protege una cuenta; esto protege el
endpoint: frena a quien prueba muchos usernames distintos desde una misma IP.

Dos formas de llavear el contador, y la diferencia importa:

- **Por IP** (`rate_limit`), que es lo que sirve cuando todavía no hay nadie
  identificado — el login es el caso.
- **Por lo que haga falta** (`consumir`), para los límites que se aplican
  después de autenticar. En un local todas las cajas salen por la misma IP,
  así que un límite solo por IP castiga al equipo entero por uno solo; ver
  `core/consulta_router.py`.

El contador, el fail-open y el corta-circuito son los mismos para las dos: dos
implementaciones del mismo mecanismo es cómo una de las dos termina sin el
fail-open, que es la parte que evita que un Redis caído cierre el restaurante.

`marcar_uso_unico` vive acá por lo mismo: es otra guarda de vida corta sobre
el mismo Redis, y duplicar el cliente y el corta-circuito para ella sería
volver a escribir la parte difícil.
"""

import time

import redis
from fastapi import HTTPException, Request, status

from src.config.settings import settings
from src.core.logging_config import logger_seguridad

logger = logger_seguridad()

# Timeout corto: si Redis no responde, el ERP no se cae esperando.
_client = redis.from_url(settings.redis_url, socket_timeout=0.2, socket_connect_timeout=0.2)

# Corta-circuito: tras un fallo, no se vuelve a intentar por unos segundos.
# Sin esto, con Redis caído cada login paga el timeout completo (~0.4 s).
PAUSA_TRAS_FALLO_SEGUNDOS = 30
_reintentar_desde = 0.0


def ip_de(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def consumir(nombre: str, sujeto: str, intentos: int, ventana_segundos: int) -> None:
    """Cuenta un uso de `sujeto` contra el límite `nombre`, o corta con 429.

    `sujeto` es lo que se está limitando: una IP, un id de usuario, lo que el
    llamador decida. `nombre` los mantiene separados en Redis — dos límites
    distintos sobre el mismo sujeto no comparten cuota.
    """
    global _reintentar_desde
    if time.monotonic() < _reintentar_desde:
        return
    clave = f"rl:{nombre}:{sujeto}"
    try:
        usados = _client.incr(clave)
        if usados == 1:
            _client.expire(clave, ventana_segundos)
    except redis.RedisError:
        # Fail-open: Redis caído no debe impedir operar el restaurante.
        _reintentar_desde = time.monotonic() + PAUSA_TRAS_FALLO_SEGUNDOS
        logger.warning("Rate limit inactivo: Redis no disponible (%s)", nombre)
        return
    if usados > intentos:
        logger.warning(
            "Rate limit superado en %s",
            nombre,
            extra={"limite": nombre, "sujeto": sujeto, "intentos": usados},
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Demasiadas solicitudes; reintentar más tarde",
            headers={"Retry-After": str(ventana_segundos)},
        )


def marcar_uso_unico(
    nombre: str, clave: str, ttl_segundos: int, marca: str = "1"
) -> bool:
    """`True` la primera vez que se ve `clave`; `False` si ya se había usado.

    Es la otra mitad de un token de un solo uso: la firma dice que el token
    es auténtico, esto dice que todavía no se gastó.

    `marca` distingue el reintento de la misma operación del reuso: si la
    clave ya estaba pero con la misma marca, es el mismo request llegando
    dos veces (un timeout de red, una tablet que reintenta) y no un replay.
    Sin eso, cada reintento obligaría al supervisor a volver al mostrador a
    teclear su PIN.

    ponytail: fail-open, igual que el contador — con Redis caído no hay
    anti-replay, pero el restaurante sigue cobrando. Ese es el techo; si
    alguna vez hace falta garantía dura, la marca va a Postgres.
    """
    global _reintentar_desde
    if time.monotonic() < _reintentar_desde:
        return True
    clave_redis = f"uso:{nombre}:{clave}"
    try:
        if _client.set(clave_redis, marca, nx=True, ex=ttl_segundos):
            return True
        previa = _client.get(clave_redis)
    except redis.RedisError:
        _reintentar_desde = time.monotonic() + PAUSA_TRAS_FALLO_SEGUNDOS
        logger.warning("Uso único inactivo: Redis no disponible (%s)", nombre)
        return True
    if isinstance(previa, bytes):
        previa = previa.decode()
    if previa == marca:
        return True
    logger.warning(
        "Reuso de una marca de un solo uso en %s",
        nombre,
        extra={"guarda": nombre, "clave": clave},
    )
    return False


def rate_limit(nombre: str, intentos: int, ventana_segundos: int):
    """Factory de dependencia FastAPI: máximo `intentos` por IP y ventana.

    ponytail: ventana fija — un pico justo en el borde deja pasar hasta 2x el
    límite. Pasar a ventana deslizante solo si el abuso real lo justifica.
    """

    def _dep(request: Request) -> None:
        consumir(nombre, ip_de(request), intentos, ventana_segundos)

    return _dep


rate_limit_login = rate_limit(
    "login",
    settings.rate_limit_login_intentos,
    settings.rate_limit_login_ventana_segundos,
)
