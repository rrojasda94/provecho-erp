"""Lectura de configuración desde el entorno.

El caso que motiva el archivo: `.env.example` documenta «listas separadas por
coma» y trae `ALLOWED_HOSTS=*`. Copiarlo a `.env` —el primer paso del README—
tumbaba el arranque con `SettingsError`, porque pydantic-settings decodifica
como JSON todo campo de tipo complejo **antes** de que corra ningún
validador, así que `_lista_por_comas` no llegaba a ejecutarse nunca. Se veía
recién al levantar `docker compose`, con la API en bucle de reinicio.
"""

import pytest

from src.config.settings import Settings


def _settings(monkeypatch, **entorno) -> Settings:
    """Construye `Settings` leyendo solo del entorno.

    `_env_file=None` evita que el `.env` de la máquina donde corre el suite se
    cuele en el test y lo haga pasar (o fallar) por lo que no es.
    """
    for clave, valor in entorno.items():
        monkeypatch.setenv(clave, valor)
    return Settings(_env_file=None)


def test_el_comodin_de_allowed_hosts_no_tumba_el_arranque(monkeypatch):
    """La línea exacta que trae `.env.example`."""
    assert _settings(monkeypatch, ALLOWED_HOSTS="*").allowed_hosts == ["*"]


def test_lista_separada_por_comas(monkeypatch):
    s = _settings(
        monkeypatch,
        ALLOWED_HOSTS="erp.provecho.pe, api.provecho.pe",
        CORS_ORIGINS="http://localhost:3000,https://erp.provecho.pe",
    )
    assert s.allowed_hosts == ["erp.provecho.pe", "api.provecho.pe"]
    assert s.cors_origins == ["http://localhost:3000", "https://erp.provecho.pe"]


def test_sigue_aceptando_la_lista_json(monkeypatch):
    """El formato que pydantic-settings resolvía antes: no se rompe a quien ya
    tenía su `.env` escrito así."""
    s = _settings(monkeypatch, ALLOWED_HOSTS='["a.pe", "b.pe"]')
    assert s.allowed_hosts == ["a.pe", "b.pe"]


def test_un_valor_vacio_no_deja_un_host_vacio(monkeypatch):
    """`ALLOWED_HOSTS=` (o con comas de más) no puede producir `[""]`: un host
    vacío en `TrustedHostMiddleware` no coincide con nada y el síntoma sería
    un 400 sin explicación."""
    assert _settings(monkeypatch, ALLOWED_HOSTS=" , ,").allowed_hosts == []


def test_sin_variables_manda_el_valor_por_defecto(monkeypatch):
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    s = Settings(_env_file=None)
    assert s.allowed_hosts == ["*"]
    assert s.cors_origins == ["http://localhost:3000"]


def test_produccion_sigue_rechazando_el_comodin(monkeypatch):
    """El arreglo de parseo no puede ablandar el endurecimiento: `*` en
    producción tiene que seguir abortando el arranque."""
    with pytest.raises(ValueError, match="ALLOWED_HOSTS"):
        _settings(
            monkeypatch,
            ENVIRONMENT="production",
            DEBUG="false",
            ALLOWED_HOSTS="*",
            CORS_ORIGINS="https://erp.provecho.pe",
            JWT_SECRET="x" * 48,
            DATABASE_URL="postgresql+psycopg://u:secreta@db:5432/provecho",
        )
