"""Logs uniformes, correlación por `request_id` y redacción de datos
sensibles antes de que salgan del proceso."""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core import sentry
from src.core.app import create_app
from src.core.logging_config import (
    NOMBRE_HANDLER,
    REDACTADO,
    FormateadorJson,
    configurar_logging,
    flujo_de,
    logger_seguridad,
    redactar,
    request_id_var,
)


def _formatear(record: logging.LogRecord) -> dict:
    return json.loads(FormateadorJson().format(record))


def _record(nombre: str = "provecho.app", **extra) -> logging.LogRecord:
    record = logging.LogRecord(nombre, logging.INFO, "f.py", 1, "hola", None, None)
    record.__dict__.update(extra)
    return record


# --- Redacción ---------------------------------------------------------------
@pytest.mark.parametrize(
    "clave",
    ["pin", "PIN", "password", "authorization", "refresh_token", "jwt_secret", "api_key"],
)
def test_redacta_claves_sensibles_sin_importar_may_min(clave: str) -> None:
    assert redactar({clave: "123456"})[clave] == REDACTADO


def test_redacta_en_estructuras_anidadas() -> None:
    entrada = {"usuario": {"nombre": "ana", "pin": "123456"}, "lista": [{"token": "t"}]}
    salida = redactar(entrada)
    assert salida["usuario"]["nombre"] == "ana"
    assert salida["usuario"]["pin"] == REDACTADO
    assert salida["lista"][0]["token"] == REDACTADO


def test_no_toca_lo_que_no_es_sensible() -> None:
    assert redactar({"venta_id": 7, "total": "12.50"}) == {"venta_id": 7, "total": "12.50"}


def test_estructura_ciclica_no_cuelga() -> None:
    """Una referencia circular no puede colgar el logger."""
    d: dict = {"a": 1}
    d["self"] = d
    assert redactar(d)["a"] == 1


# --- Formato JSON ------------------------------------------------------------
def test_el_log_json_trae_los_campos_del_contrato() -> None:
    evento = _formatear(_record())
    assert set(evento) >= {"ts", "nivel", "flujo", "logger", "mensaje", "app", "entorno"}
    assert evento["mensaje"] == "hola"


def test_el_contexto_extra_se_redacta_en_el_log() -> None:
    """Un `extra={"pin": ...}` descuidado no puede terminar en el colector."""
    evento = _formatear(_record(pin="123456", venta_id="v-1"))
    assert evento["contexto"]["pin"] == REDACTADO
    assert evento["contexto"]["venta_id"] == "v-1"


def test_el_log_lleva_el_request_id_vigente() -> None:
    testigo = request_id_var.set("abc123")
    try:
        assert _formatear(_record())["request_id"] == "abc123"
    finally:
        request_id_var.reset(testigo)


def test_sin_request_id_no_se_inventa_el_campo() -> None:
    assert "request_id" not in _formatear(_record())


def test_la_excepcion_viaja_con_su_traza() -> None:
    try:
        raise ValueError("se rompió")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "provecho.app", logging.ERROR, "f.py", 1, "falló", None, sys.exc_info()
        )
    assert "ValueError: se rompió" in _formatear(record)["excepcion"]


@pytest.mark.parametrize(
    ("logger", "esperado"),
    [
        ("provecho.seguridad", "seguridad"),
        ("provecho.seguridad.login", "seguridad"),
        ("provecho.auditoria", "auditoria"),
        ("provecho.app", "app"),
        ("src.modules.sales.tasks", "app"),
        ("provecho.inventado", "app"),
    ],
)
def test_el_flujo_sale_del_nombre_del_logger(logger: str, esperado: str) -> None:
    assert flujo_de(logger) == esperado


def test_logger_de_seguridad_pertenece_a_su_flujo() -> None:
    assert flujo_de(logger_seguridad().name) == "seguridad"


def test_configurar_logging_es_idempotente() -> None:
    """Se llama en el arranque de la API, del worker y de los comandos: no
    puede acumular handlers ni duplicar cada línea."""
    configurar_logging()
    configurar_logging()
    propios = [
        h for h in logging.getLogger().handlers if h.get_name() == NOMBRE_HANDLER
    ]
    assert len(propios) == 1


def test_configurar_logging_respeta_handlers_ajenos() -> None:
    """No puede desconectar al que ya estaba escuchando (pytest, un
    colector externo): solo retira el suyo."""
    ajeno = logging.NullHandler()
    ajeno.set_name("ajeno")
    logging.getLogger().addHandler(ajeno)
    try:
        configurar_logging()
        assert ajeno in logging.getLogger().handlers
    finally:
        logging.getLogger().removeHandler(ajeno)


# --- Correlación en la API ---------------------------------------------------
def test_toda_respuesta_lleva_request_id() -> None:
    respuesta = TestClient(create_app()).get("/health")
    assert len(respuesta.headers["X-Request-ID"]) == 32


def test_se_respeta_el_request_id_entrante() -> None:
    """Permite seguir una traza que ya venía del proxy o del frontend."""
    respuesta = TestClient(create_app()).get(
        "/health", headers={"X-Request-ID": "traza-del-proxy"}
    )
    assert respuesta.headers["X-Request-ID"] == "traza-del-proxy"


def test_cada_request_recibe_un_id_distinto() -> None:
    client = TestClient(create_app())
    primero = client.get("/health").headers["X-Request-ID"]
    assert client.get("/health").headers["X-Request-ID"] != primero


def test_un_error_no_controlado_devuelve_su_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sin ese identificador, un "me dio error" del usuario no se puede
    cruzar con ningún log."""
    app = create_app()

    @app.get("/api/v1/_boom")
    def _boom() -> None:
        raise RuntimeError("algo explotó")

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        respuesta = client.get("/api/v1/_boom", headers={"X-Request-ID": "rid-42"})

    assert respuesta.status_code == 500
    assert respuesta.json() == {"detail": "Error interno", "request_id": "rid-42"}
    assert respuesta.headers["X-Request-ID"] == "rid-42"
    assert "algo explotó" in caplog.text


def test_el_error_no_filtra_detalles_internos() -> None:
    app = create_app()

    @app.get("/api/v1/_boom2")
    def _boom() -> None:
        raise RuntimeError("password=secreto123 en la conexión")

    respuesta = TestClient(app, raise_server_exceptions=False).get("/api/v1/_boom2")
    assert "secreto123" not in respuesta.text


# --- Sentry ------------------------------------------------------------------
def test_sin_dsn_no_se_inicia_sentry(monkeypatch: pytest.MonkeyPatch) -> None:
    """En local y en tests no debe salir un solo byte a un tercero."""
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "sentry_dsn", "")
    monkeypatch.setattr(sentry, "_iniciado", False)
    assert sentry.iniciar_sentry("api") is False


def test_reportar_sin_sentry_no_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sentry, "_iniciado", False)
    sentry.reportar(ValueError("x"))  # no debe lanzar


def test_el_evento_a_sentry_va_redactado() -> None:
    """Un reporte de error es el lugar más fácil para filtrar un PIN."""
    evento = sentry._limpiar_evento(
        {
            "request": {
                "headers": {"Authorization": "Bearer abc", "Cookie": "s=1", "Host": "x"}
            },
            "extra": {"pin": "123456", "venta_id": "v-1"},
        },
        {},
    )
    assert evento["request"]["headers"]["Authorization"] == REDACTADO
    assert evento["request"]["headers"]["Cookie"] == REDACTADO
    assert evento["request"]["headers"]["Host"] == "x"
    assert evento["extra"]["pin"] == REDACTADO
    assert evento["extra"]["venta_id"] == "v-1"


def test_la_app_arranca_sin_configuracion_de_observabilidad() -> None:
    """Todo esto es opcional: sin DSN ni nada, la API sigue levantando."""
    assert isinstance(create_app(), FastAPI)
