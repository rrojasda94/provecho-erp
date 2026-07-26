"""Rate limiting por IP con contador en Redis (ventana fija).

El lockout de `usuario` (5 intentos) protege una cuenta; esto protege el
endpoint: frena a quien prueba muchos usernames distintos desde una misma IP.
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


def rate_limit(nombre: str, intentos: int, ventana_segundos: int):
    """Factory de dependencia FastAPI: máximo `intentos` por IP y ventana.

    ponytail: ventana fija — un pico justo en el borde deja pasar hasta 2x el
    límite. Pasar a ventana deslizante solo si el abuso real lo justifica.
    """

    def _dep(request: Request) -> None:
        global _reintentar_desde
        if time.monotonic() < _reintentar_desde:
            return
        ip = request.client.host if request.client else "desconocida"
        clave = f"rl:{nombre}:{ip}"
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
                extra={"limite": nombre, "ip": ip, "intentos": usados},
            )
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Demasiadas solicitudes; reintentar más tarde",
                headers={"Retry-After": str(ventana_segundos)},
            )

    return _dep


rate_limit_login = rate_limit(
    "login",
    settings.rate_limit_login_intentos,
    settings.rate_limit_login_ventana_segundos,
)
