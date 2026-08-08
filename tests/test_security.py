"""Endurecimiento: validación de configuración de producción, rate limit por
IP y cabeceras de seguridad."""

import pytest
import redis
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.core import rate_limit as rl
from src.core.app import create_app
from src.core.database import CONNECT_TIMEOUT_SEGUNDOS, connect_args
from tests.conftest import HASHER_PRODUCCION, RedisFalso

_PROD_OK = {
    "environment": "production",
    "debug": False,
    "jwt_secret": "x" * 48,
    "database_url": "postgresql+psycopg://provecho:s3cr3t@db:5432/provecho",
    "allowed_hosts": ["erp.majambo.pe"],
    "cors_origins": ["https://erp.majambo.pe"],
}


def _settings(**overrides) -> Settings:
    # _env_file=None: ignora el .env del desarrollador, el test fija todo.
    return Settings(_env_file=None, **{**_PROD_OK, **overrides})


def test_produccion_valida_arranca() -> None:
    assert _settings().es_produccion is True


@pytest.mark.parametrize(
    ("override", "esperado"),
    [
        ({"jwt_secret": "change-me"}, "placeholder"),
        ({"jwt_secret": "corto"}, "32 caracteres"),
        ({"debug": True}, "DEBUG"),
        (
            {"database_url": "postgresql+psycopg://provecho:provecho@db:5432/provecho"},
            "contraseña por defecto",
        ),
        ({"allowed_hosts": ["*"]}, "ALLOWED_HOSTS"),
        ({"cors_origins": ["*"]}, "CORS_ORIGINS"),
    ],
)
def test_produccion_insegura_no_arranca(override: dict, esperado: str) -> None:
    with pytest.raises(ValueError, match=esperado):
        _settings(**override)


def test_local_tolera_valores_de_desarrollo() -> None:
    """Los mismos valores que revientan producción son válidos en local."""
    assert _settings(environment="local", jwt_secret="change-me").es_produccion is False


def test_listas_aceptan_texto_separado_por_comas() -> None:
    s = _settings(allowed_hosts="a.pe, b.pe", cors_origins="https://a.pe")
    assert s.allowed_hosts == ["a.pe", "b.pe"]
    assert s.cors_origins == ["https://a.pe"]


class _RedisCaido:
    def __init__(self) -> None:
        self.intentos = 0

    def incr(self, clave: str) -> int:
        self.intentos += 1
        raise redis.RedisError("sin conexión")

    def expire(self, clave: str, segundos: int) -> None:
        raise redis.RedisError("sin conexión")


def _app_con_limite(intentos: int) -> TestClient:
    app = FastAPI()
    limite = Depends(rl.rate_limit("test", intentos, 60))

    @app.get("/ping", dependencies=[limite])
    def _ping() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        (
            "postgresql+psycopg://provecho:s3cr3t@db:5432/provecho",
            {"connect_timeout": CONNECT_TIMEOUT_SEGUNDOS},
        ),
        ("postgresql://provecho:s3cr3t@db:5432/provecho", {"connect_timeout": 5}),
        # El `e2e` arranca la API contra un SQLite desechable y su driver no
        # entiende `connect_timeout`: pasárselo mata el arranque.
        ("sqlite:///./e2e.db", {}),
    ],
)
def test_solo_postgres_recibe_connect_timeout(url: str, esperado: dict) -> None:
    """Sin timeout, un Postgres que acepta el TCP y se calla clava el request
    para siempre (ver CHANGELOG 2026-08-08)."""
    assert connect_args(url) == esperado


def test_seguridad_del_hasher_de_produccion() -> None:
    """El suite corre con Argon2id abaratado (`_argon2_barato` en conftest);
    este es el único lugar que mira los parámetros reales. Piso: perfil de
    baja memoria de la RFC 9106 (t=3, m=64 MiB)."""
    assert HASHER_PRODUCCION.time_cost >= 3
    assert HASHER_PRODUCCION.memory_cost >= 64 * 1024
    assert HASHER_PRODUCCION.parallelism >= 1


def test_rate_limit_bloquea_tras_el_maximo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "_client", RedisFalso())
    client = _app_con_limite(3)
    assert [client.get("/ping").status_code for _ in range(3)] == [200, 200, 200]
    respuesta = client.get("/ping")
    assert respuesta.status_code == 429
    assert respuesta.headers["Retry-After"] == "60"


def test_rate_limit_falla_abierto_si_redis_no_responde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis caído no puede dejar sin operar al restaurante, y el
    corta-circuito evita pagar el timeout en cada request siguiente."""
    caido = _RedisCaido()
    monkeypatch.setattr(rl, "_client", caido)
    client = _app_con_limite(1)
    assert [client.get("/ping").status_code for _ in range(5)] == [200] * 5
    assert caido.intentos == 1


def test_cabeceras_de_seguridad_presentes() -> None:
    respuesta = TestClient(create_app()).get("/health")
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert respuesta.headers["Referrer-Policy"] == "no-referrer"


def test_hsts_y_docs_solo_fuera_de_produccion(monkeypatch: pytest.MonkeyPatch) -> None:
    """En local hay /docs y no hay HSTS; en producción, al revés."""
    from src.config import settings as modulo_settings

    respuesta = TestClient(create_app()).get("/health")
    assert "Strict-Transport-Security" not in respuesta.headers

    monkeypatch.setattr(modulo_settings.settings, "environment", "production")
    app = create_app()
    assert app.docs_url is None
    assert app.openapi_url is None
    assert "Strict-Transport-Security" in TestClient(app).get("/health").headers
