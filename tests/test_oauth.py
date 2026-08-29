"""OAuth2 (Authorization Code) del SSO del BI — `src/core/oauth/` (ADR-083
Fase B).

`/oauth/codigo` es el único de los tres endpoints con sesión de Provecho de
por medio (JWT + `bi.acceder`); `/token` y `/userinfo` son servidor-a-
servidor y se prueban sin ningún token de Provecho, como los llamaría
Superset de verdad.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.app import create_app
from src.core.database import Base
from src.core.oauth import servicio
from src.modules.users.api.deps import get_db

CLIENT_ID = "superset-test"
CLIENT_SECRET = "secreto-de-prueba"
REDIRECT_URI = "https://bi.majambo.com.pe/oauth-authorized/provecho"


class _RedisOAuthFalso:
    """Mismo criterio que `RedisFalso` de `conftest.py` para el rate limit:
    superficie mínima que usa `servicio.py`, en memoria de proceso — ningún
    test de este archivo habla con un Redis real."""

    def __init__(self) -> None:
        self.claves: dict[str, bytes] = {}

    def setex(self, clave: str, _ttl: int, valor) -> None:
        self.claves[clave] = valor.encode() if isinstance(valor, str) else valor

    def get(self, clave: str):
        return self.claves.get(clave)

    def getdel(self, clave: str):
        return self.claves.pop(clave, None)


@pytest.fixture(autouse=True)
def _redis_oauth_en_memoria(monkeypatch):
    monkeypatch.setattr(servicio, "_client", _RedisOAuthFalso())


@pytest.fixture(autouse=True)
def _cliente_configurado(monkeypatch):
    monkeypatch.setattr(settings, "oauth_bi_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "oauth_bi_client_secret", CLIENT_SECRET)
    monkeypatch.setattr(settings, "oauth_bi_redirect_uri", REDIRECT_URI)


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    with TestSession() as s:
        seed(s)
        s.commit()

    app = create_app()

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c


def _token(client: TestClient, username="admin", pin="123456") -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(client: TestClient, username="admin", pin="123456") -> dict:
    return {"Authorization": f"Bearer {_token(client, username, pin)}"}


def _emitir_codigo(client: TestClient, headers: dict) -> str:
    r = client.post(
        "/api/v1/oauth/codigo",
        headers=headers,
        json={"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI},
    )
    assert r.status_code == 200, r.text
    return r.json()["codigo"]


def _canjear(client: TestClient, codigo: str, **overrides):
    body = {
        "grant_type": "authorization_code",
        "code": codigo,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        **overrides,
    }
    return client.post("/api/v1/oauth/token", data=body)


def test_codigo_exige_bi_acceder(env):
    # cajero1 (RN-BI-004): sin `bi.acceder` ni siquiera se emite el código.
    headers = _headers(env, username="cajero1", pin="123456")
    r = env.post(
        "/api/v1/oauth/codigo",
        headers=headers,
        json={"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI},
    )
    assert r.status_code == 403


def test_codigo_sin_sesion_401(env):
    r = env.post(
        "/api/v1/oauth/codigo",
        json={"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI},
    )
    assert r.status_code == 401


def test_redirect_uri_que_no_coincide_no_emite_codigo(env):
    headers = _headers(env)
    r = env.post(
        "/api/v1/oauth/codigo",
        headers=headers,
        json={"client_id": CLIENT_ID, "redirect_uri": "https://otro-destino.example/cb"},
    )
    assert r.status_code == 400


def test_client_id_desconocido_no_emite_codigo(env):
    headers = _headers(env)
    r = env.post(
        "/api/v1/oauth/codigo",
        headers=headers,
        json={"client_id": "otro-cliente", "redirect_uri": REDIRECT_URI},
    )
    assert r.status_code == 400


def test_sin_client_secret_configurado_el_sso_queda_apagado(env, monkeypatch):
    """Un despliegue que se olvida de `OAUTH_BI_CLIENT_SECRET` no deja el
    SSO abierto — lo deja cerrado. Es la garantía explícita del comentario en
    `settings.py`."""
    monkeypatch.setattr(settings, "oauth_bi_client_secret", "")
    headers = _headers(env)
    r = env.post(
        "/api/v1/oauth/codigo",
        headers=headers,
        json={"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI},
    )
    assert r.status_code == 400


def test_flujo_completo_codigo_token_userinfo(env):
    headers = _headers(env)
    codigo = _emitir_codigo(env, headers)

    r = _canjear(env, codigo)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] > 0
    access_token = cuerpo["access_token"]

    r = env.get(
        "/api/v1/oauth/userinfo", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 200, r.text
    info = r.json()
    assert info["preferred_username"] == "admin"
    assert "admin" in info["roles"]
    uuid.UUID(info["sub"])  # no revienta: es un UUID de verdad


def test_el_codigo_es_de_un_solo_uso(env):
    headers = _headers(env)
    codigo = _emitir_codigo(env, headers)

    primero = _canjear(env, codigo)
    assert primero.status_code == 200, primero.text

    segundo = _canjear(env, codigo)
    assert segundo.status_code == 400


def test_token_con_client_secret_incorrecto_falla(env):
    headers = _headers(env)
    codigo = _emitir_codigo(env, headers)

    r = _canjear(env, codigo, client_secret="lo-que-sea")
    assert r.status_code == 400


def test_token_con_redirect_uri_distinto_al_emitido_falla(env):
    headers = _headers(env)
    codigo = _emitir_codigo(env, headers)

    r = _canjear(env, codigo, redirect_uri="https://otro-destino.example/cb")
    assert r.status_code == 400


def test_token_con_grant_type_no_soportado_falla(env):
    headers = _headers(env)
    codigo = _emitir_codigo(env, headers)

    r = _canjear(env, codigo, grant_type="client_credentials")
    assert r.status_code == 400


def test_userinfo_sin_bearer_401(env):
    r = env.get("/api/v1/oauth/userinfo")
    assert r.status_code == 401


def test_userinfo_con_token_inventado_401(env):
    r = env.get(
        "/api/v1/oauth/userinfo", headers={"Authorization": "Bearer no-existo"}
    )
    assert r.status_code == 401
