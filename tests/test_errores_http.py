"""Mapeo de errores de aplicación a HTTP, ahora en un solo lugar.

Antes vivía duplicado en los ocho routers y las copias se habían separado:
seis resolvían por `type(err)` exacto, así que una subclase
(`StockInsuficiente`, `PrecioNoDefinido`) habría caído al 400 genérico en
vez de heredar el estado de su base. Estos tests fijan el comportamiento
correcto para que no vuelva a divergir.
"""

from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Query, status
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, field_validator

from src.core import error_handlers, validacion
from src.modules.inventory.application.errors import StockInsuficiente
from src.modules.sales.application.errors import PrecioNoDefinido
from src.modules.users.api import error_handlers as users_error_handlers
from src.modules.users.application.errors import (
    CredencialesInvalidas,
    PinInvalido,
    TokenInvalido,
    UsuarioBloqueado,
)
from src.shared import etiquetas
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


# --- 422: la validación de entrada, dicha en español ---------------------------
#
# Antes salía el formato crudo de FastAPI (`detail` como lista de `{loc, msg,
# type}` en inglés) y el frontend lo mostraba como "Field required; Field
# required": tres campos mal cargados, tres veces el mismo texto y ninguna
# mención del campo. Estos tests fijan el sobre nuevo.


@pytest.mark.parametrize(
    ("campo", "esperado"),
    [
        ("codigo", "Código"),
        ("almacen_id", "Almacén"),
        ("unidad_medida_id", "Unidad de medida"),
        ("ruc", "RUC"),
        ("page_size", "Tamaño de página"),
        ("razon_social", "Razón social"),
        # Regla de sufijo: no hace falta una entrada por cada -ción.
        ("autorizacion_id", "Autorización"),
        # Plural: va sin tilde y la regla no lo toca.
        ("observaciones", "Observaciones"),
        # El índice y el camino ya viajan en `campo`; la etiqueta es del campo.
        ("items[0].cantidad", "Cantidad"),
        # Sin entrada ni regla: limpieza automática, nunca un KeyError.
        ("nombre_fantasia", "Nombre fantasia"),
    ],
)
def test_etiqueta_de_campo(campo, esperado) -> None:
    assert etiquetas.etiqueta(campo) == esperado


class _Linea(BaseModel):
    cantidad: Decimal = Field(gt=0)


class _Cuerpo(BaseModel):
    codigo: str = Field(max_length=5)
    modulo: Literal["compras", "rrhh"]
    almacen_id: UUID
    lineas: list[_Linea]

    @field_validator("codigo")
    @classmethod
    def _sin_espacios(cls, v: str) -> str:
        if " " in v:
            raise ValueError("no puede llevar espacios")
        return v


@pytest.fixture()
def client_validacion():
    app = FastAPI()
    validacion.registrar(app)

    @app.post("/cuerpo")
    def _cuerpo(c: _Cuerpo):  # pragma: no cover - nunca llega con entrada mala
        return {}

    @app.get("/borde/{uid}")
    def _borde(uid: UUID, page_size: int = Query(default=1, le=200)):  # pragma: no cover
        return {}

    with TestClient(app) as c:
        yield c


def test_el_detalle_nombra_cada_campo_en_espanol(client_validacion) -> None:
    r = client_validacion.post(
        "/cuerpo",
        json={"codigo": "demasiado largo", "modulo": "ventas", "lineas": [{"cantidad": "0"}]},
    )
    assert r.status_code == 422
    cuerpo = r.json()
    assert isinstance(cuerpo["detail"], str)
    assert cuerpo["detail"] == (
        "Código: máximo 5 caracteres; "
        "Módulo: valor no válido: se espera 'compras' o 'rrhh'; "
        "Almacén: obligatorio; "
        "Cantidad: debe ser mayor que 0"
    )
    assert cuerpo["errores"][2] == {
        "campo": "almacen_id",
        "etiqueta": "Almacén",
        "mensaje": "obligatorio",
    }
    # El campo anidado conserva su ruta: es lo que necesita el formulario.
    assert cuerpo["errores"][3]["campo"] == "lineas[0].cantidad"


def test_el_mensaje_de_un_validador_propio_pasa_sin_el_prefijo(client_validacion) -> None:
    """Nuestros `field_validator` ya escriben en español; Pydantic les
    antepone `Value error, ` y eso es ruido en pantalla."""
    r = client_validacion.post(
        "/cuerpo",
        json={"codigo": "a b", "modulo": "rrhh", "almacen_id": str(uuid4()), "lineas": []},
    )
    assert r.json()["detail"] == "Código: no puede llevar espacios"


def test_cuerpo_no_json_no_deja_el_mensaje_sin_sujeto(client_validacion) -> None:
    """`json_invalid` trae en `loc` la posición del carácter, no un campo."""
    r = client_validacion.post(
        "/cuerpo", content="no soy json", headers={"Content-Type": "application/json"}
    )
    assert r.json() == {
        "detail": "el cuerpo no es JSON válido",
        "errores": [{"campo": "", "etiqueta": "Cuerpo", "mensaje": "el cuerpo no es JSON válido"}],
    }


def test_path_y_query_tambien_se_traducen(client_validacion) -> None:
    r = client_validacion.get("/borde/no-es-uuid?page_size=500")
    assert r.json()["detail"] == (
        "Uid: identificador no válido; Tamaño de página: debe ser menor o igual que 200"
    )


def test_un_tipo_sin_traduccion_cae_al_mensaje_original() -> None:
    """Quedar en inglés es peor que perder el dato, no al revés."""
    assert validacion.mensaje_de({"type": "inventado", "msg": "Something odd"}) == "Something odd"


def test_una_plantilla_sin_su_ctx_no_revienta_el_handler() -> None:
    """Si Pydantic cambiara el `ctx` de un `type`, el manejador de errores no
    puede ser el que lance el error."""
    assert validacion.mensaje_de({"type": "greater_than", "msg": "must be > 0"}) == "must be > 0"


def test_el_sobre_admite_un_422_sin_campos() -> None:
    """`PinInvalido` y los `HTTPException(422)` de los routers responden solo
    `detail`: el schema del contrato tiene que seguir describiéndolos."""
    assert validacion.ErrorValidacion(detail="PIN inválido").errores == []
