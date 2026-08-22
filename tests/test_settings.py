"""Lectura de configuración desde el entorno.

El caso que motiva el archivo: `.env.example` documenta «listas separadas por
coma» y trae `ALLOWED_HOSTS=*`. Copiarlo a `.env` —el primer paso del README—
tumbaba el arranque con `SettingsError`, porque pydantic-settings decodifica
como JSON todo campo de tipo complejo **antes** de que corra ningún
validador, así que `_lista_por_comas` no llegaba a ejecutarse nunca. Se veía
recién al levantar `docker compose`, con la API en bucle de reinicio.
"""

import pathlib
import re

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


# --- Sincronía entre `Settings` y los `.env.example` -------------------------
# El archivo de ejemplo es la única documentación operativa de cómo se
# configura el ERP: si una variable existe en el código y nadie la escribió
# ahí, en la práctica no existe — se descubre el día que hace falta, en
# producción. La deriva no la ve ruff ni el type checker, por eso se prueba.

_RAIZ = pathlib.Path(__file__).resolve().parents[1]
# Campos internos que a propósito NO se exponen: nadie los ajusta por entorno
# y ofrecerlos en el ejemplo solo invita a romper cosas.
_NO_SE_DOCUMENTAN = {"APP_NAME", "APP_VERSION", "JWT_ALGORITHM"}


def _variables(nombre_archivo: str) -> set[str]:
    """Nombres declarados en un `.env`, incluidas las líneas comentadas (una
    variable comentada sigue estando documentada: dice qué poner y cuándo)."""
    texto = (_RAIZ / nombre_archivo).read_text(encoding="utf-8")
    return {
        linea.split("=", 1)[0].lstrip("# ").strip()
        for linea in texto.splitlines()
        if re.match(r"^#?\s*[A-Z][A-Z0-9_]*=", linea)
    }


def test_toda_variable_de_settings_esta_documentada():
    """El hub tiene su propio ejemplo, así que vale que la variable esté en
    cualquiera de los dos."""
    documentadas = _variables(".env.example") | _variables(".env.hub.example")
    del_codigo = {nombre.upper() for nombre in Settings.model_fields}
    faltan = del_codigo - documentadas - _NO_SE_DOCUMENTAN
    assert not faltan, f"sin documentar en .env.example: {sorted(faltan)}"


def test_el_ejemplo_no_lleva_secretos_de_verdad():
    """`.env.example` SÍ se commitea. Un JWT o una API key de Google copiados
    del `.env` real quedan en el historial de git para siempre, y rotarlos
    después es un trámite con el proveedor, no un `git revert`."""
    texto = (_RAIZ / ".env.example").read_text(encoding="utf-8")
    sospechosos = re.findall(r"eyJ[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}", texto)
    assert not sospechosos, "hay credenciales reales en .env.example"


def test_el_ejemplo_copiado_tal_cual_arranca():
    """`cp .env.example .env` es el primer paso del README. Un valor mal
    escrito ahí (un decimal con coma, un entero con unidad) no lo ve nadie
    hasta que la API entra en bucle de reinicio."""
    Settings(_env_file=_RAIZ / ".env.example")
