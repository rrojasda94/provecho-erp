"""Estados HTTP propios de la autenticación de cuenta del sitio (ADR-102).
Mismo patrón que `users.api.error_handlers`."""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.core.error_handlers import Mapeo, estado_http, responder
from src.modules.storefront.application.errors import (
    CredencialesInvalidas,
    CuentaBloqueada,
    TokenInvalido,
)

_MAPEO: Mapeo = (
    (CredencialesInvalidas, status.HTTP_401_UNAUTHORIZED),
    (TokenInvalido, status.HTTP_401_UNAUTHORIZED),
    (CuentaBloqueada, status.HTTP_423_LOCKED),
)


def http_exception(error: Exception) -> HTTPException:
    """Para el login: hay que commitear el intento fallido/lockout ANTES de
    fallar, así que el router lo atrapa y lo relanza con esto en vez de
    dejarlo caer al handler global (que llega después del rollback
    automático de `get_db`). Mismo patrón que `users.api.error_handlers`."""
    return HTTPException(estado_http(error, _MAPEO), str(error))


def registrar(app: FastAPI) -> None:
    for tipo, _ in _MAPEO:

        @app.exception_handler(tipo)
        async def _auth_error(request: Request, exc: Exception) -> JSONResponse:
            return responder(exc, _MAPEO)
