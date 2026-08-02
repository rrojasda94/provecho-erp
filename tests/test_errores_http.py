"""Mapeo de errores de aplicación a HTTP, ahora en un solo lugar.

Antes vivía duplicado en los ocho routers y las copias se habían separado:
seis resolvían por `type(err)` exacto, así que una subclase
(`StockInsuficiente`, `PrecioNoDefinido`) habría caído al 400 genérico en
vez de heredar el estado de su base. Estos tests fijan el comportamiento
correcto para que no vuelva a divergir.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.core import error_handlers
from src.modules.inventory.application.errors import StockInsuficiente
from src.modules.sales.application.errors import PrecioNoDefinido
from src.modules.users.api import error_handlers as users_error_handlers
from src.modules.users.application.errors import (
    CredencialesInvalidas,
    PinInvalido,
    TokenInvalido,
    UsuarioBloqueado,
)
from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio


@pytest.mark.parametrize(
    ("error", "esperado"),
    [
        (NoEncontrado("x"), status.HTTP_404_NOT_FOUND),
        (Conflicto("x"), status.HTTP_409_CONFLICT),
        (ReglaNegocio("x"), status.HTTP_409_CONFLICT),
        # Subclases: heredan el estado de su base, no caen al 400.
        (StockInsuficiente("x"), status.HTTP_409_CONFLICT),
        (PrecioNoDefinido("x"), status.HTTP_409_CONFLICT),
        # Un AppError sin especializar es un 400.
        (AppError("x"), status.HTTP_400_BAD_REQUEST),
    ],
)
def test_estado_generico(error, esperado) -> None:
    assert error_handlers.estado_http(error) == esperado


@pytest.mark.parametrize(
    ("error", "esperado"),
    [
        (CredencialesInvalidas("x"), status.HTTP_401_UNAUTHORIZED),
        (TokenInvalido("x"), status.HTTP_401_UNAUTHORIZED),
        (UsuarioBloqueado("x"), status.HTTP_423_LOCKED),
        (PinInvalido("x"), 422),
    ],
)
def test_estados_propios_de_users(error, esperado) -> None:
    assert users_error_handlers.http_exception(error).status_code == esperado


@pytest.fixture()
def client():
    """App mínima: interesa el handler, no los routers reales."""
    app = FastAPI()
    error_handlers.registrar(app)
    users_error_handlers.registrar(app)

    @app.get("/no-encontrado")
    def _no_encontrado():
        raise NoEncontrado("no existe")

    @app.get("/subclase")
    def _subclase():
        raise StockInsuficiente("stock insuficiente de sku X")

    @app.get("/credenciales")
    def _credenciales():
        raise CredencialesInvalidas("Credenciales inválidas")

    with TestClient(app) as c:
        yield c


def test_endpoint_sin_try_except_devuelve_404(client) -> None:
    """La razón de ser del handler global: un endpoint que no envuelve nada
    ya no responde 500 por olvidarse del `except`."""
    r = client.get("/no-encontrado")
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json() == {"detail": "no existe"}


def test_subclase_de_regla_negocio_devuelve_409(client) -> None:
    r = client.get("/subclase")
    assert r.status_code == status.HTTP_409_CONFLICT


def test_handler_de_users_gana_al_generico(client) -> None:
    """Ambos handlers están registrados; Starlette resuelve por MRO y el
    más específico se queda con el 401."""
    r = client.get("/credenciales")
    assert r.status_code == status.HTTP_401_UNAUTHORIZED
