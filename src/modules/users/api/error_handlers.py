"""Estados HTTP propios de la autenticación de users.

`core/error_handlers` cubre la tripleta común (404/409). Estos cuatro son
específicos del módulo, y por eso los registra el módulo: el handler más
específico gana por MRO, así que un `CredencialesInvalidas` cae acá y un
`NoEncontrado` de users sigue cayendo en el genérico.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.core.error_handlers import Mapeo, estado_http, responder
from src.modules.users.application.errors import (
    CredencialesInvalidas,
    PinInvalido,
    TokenInvalido,
    UsuarioBloqueado,
)

_MAPEO: Mapeo = (
    (CredencialesInvalidas, status.HTTP_401_UNAUTHORIZED),
    (TokenInvalido, status.HTTP_401_UNAUTHORIZED),
    (UsuarioBloqueado, status.HTTP_423_LOCKED),
    (PinInvalido, 422),  # literal: la constante de Starlette cambió de nombre
)


def http_exception(error: Exception) -> HTTPException:
    """Para los pocos endpoints que necesitan commitear *antes* de fallar
    (persistir un intento fallido, revocar una cadena de refresh) y por eso
    no pueden delegar en el handler global."""
    return HTTPException(estado_http(error, _MAPEO), str(error))


def registrar(app: FastAPI) -> None:
    for tipo, _ in _MAPEO:

        @app.exception_handler(tipo)
        async def _auth_error(request: Request, exc: Exception) -> JSONResponse:
            return responder(exc, _MAPEO)
