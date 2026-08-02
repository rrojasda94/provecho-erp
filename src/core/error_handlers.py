"""Traducción de errores de aplicación a HTTP. Único lugar donde ocurre.

Antes cada router traía su copia de `_HTTP_STATUS` + `_http()` y cada
endpoint envolvía la llamada en un `try/except` cuyo único cuerpo era
`raise _http(e)`. Ochenta y seis repeticiones del mismo gesto, y un
endpoint nuevo que olvidara el `except` devolvía 500 en vez de 404.

Acá viven los tres estados que valen para cualquier módulo. Un módulo con
semántica HTTP propia (users: 401/423 de autenticación) registra su propio
handler desde su capa `api` — Starlette resuelve por el MRO de la
excepción, así que el handler más específico gana. `core` no tiene por qué
conocer los errores de nadie.

La sesión ya se deshace sola: la dependencia `get_db` hace rollback ante
cualquier excepción del endpoint y su cierre corre antes que estos
handlers.
"""

from collections.abc import Sequence

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

Mapeo = Sequence[tuple[type[AppError], int]]

# Se resuelve por `isinstance` y gana la primera coincidencia: las
# subclases van antes que sus bases.
_GENERICO: Mapeo = (
    (NoEncontrado, status.HTTP_404_NOT_FOUND),
    (Conflicto, status.HTTP_409_CONFLICT),
    (ReglaNegocio, status.HTTP_409_CONFLICT),
)

POR_DEFECTO = status.HTTP_400_BAD_REQUEST


def estado_http(error: AppError, mapeo: Mapeo = _GENERICO) -> int:
    for tipo, codigo in mapeo:
        if isinstance(error, tipo):
            return codigo
    return POR_DEFECTO


def responder(error: AppError, mapeo: Mapeo = _GENERICO) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=estado_http(error, mapeo))


def registrar(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return responder(exc)
