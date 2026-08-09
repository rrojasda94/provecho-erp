"""Auth por token de una cuenta `agente_ia`: emisión, uso, revocación,
vencimiento y el hecho de que el RBAC no cambia por usar otra credencial.

SQLite en memoria + seeder, mismo montaje que `test_users_auth.py`.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401  (puebla Base.metadata)
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import TokenAgente, Usuario
from tests.conftest import auth_headers


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
        cabeceras = auth_headers(s)
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
        yield c, cabeceras, TestSession


def _crear_agente(client, headers, username="bot_pedidos"):
    r = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": username,
            "pin": "123456",
            "tipo": "agente_ia",
            "nombre_display": "Bot de pedidos",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _emitir_token(client, headers, usuario_id, **extra):
    return client.post(
        f"/api/v1/users/{usuario_id}/tokens",
        headers=headers,
        json={"nombre": "n8n producción", **extra},
    )


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_token_emitido_autentica(env):
    client, headers, _ = env
    agente_id = _crear_agente(client, headers)

    r = _emitir_token(client, headers, agente_id)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["token"].startswith("prv_")
    assert cuerpo["prefijo"] == cuerpo["token"][:12]

    yo = client.get("/api/v1/users/me", headers=_bearer(cuerpo["token"]))
    assert yo.status_code == 200
    assert yo.json()["username"] == "bot_pedidos"
    assert yo.json()["tipo"] == "agente_ia"


def test_el_token_en_claro_no_vuelve_a_salir(env):
    client, headers, _ = env
    agente_id = _crear_agente(client, headers)
    raw = _emitir_token(client, headers, agente_id).json()["token"]

    listado = client.get(f"/api/v1/users/{agente_id}/tokens", headers=headers)
    assert listado.status_code == 200
    fila = listado.json()[0]
    assert "token" not in fila
    assert raw not in str(fila)


def test_token_conserva_el_rbac_del_usuario(env):
    """La credencial dice quién es, no qué puede: el rol `agente_ia` solo
    tiene `sales.crear_pedido`, así que la administración le sigue negada."""
    client, headers, _ = env
    agente_id = _crear_agente(client, headers)
    roles = client.get("/api/v1/roles", headers=headers).json()
    rol_id = next(r["id"] for r in roles if r["nombre"] == "agente_ia")
    assert (
        client.post(
            f"/api/v1/users/{agente_id}/roles",
            headers=headers,
            json={"rol_id": rol_id},
        ).status_code
        == 204
    )
    agente = _bearer(_emitir_token(client, headers, agente_id).json()["token"])

    assert client.get("/api/v1/users/me", headers=agente).status_code == 200
    assert client.get("/api/v1/users", headers=agente).status_code == 403


def test_token_revocado_401(env):
    client, headers, _ = env
    agente_id = _crear_agente(client, headers)
    creado = _emitir_token(client, headers, agente_id).json()
    agente = _bearer(creado["token"])
    assert client.get("/api/v1/users/me", headers=agente).status_code == 200

    ruta = f"/api/v1/users/{agente_id}/tokens/{creado['id']}"
    assert client.delete(ruta, headers=headers).status_code == 204
    assert client.get("/api/v1/users/me", headers=agente).status_code == 401
    # Idempotente: revocar de nuevo no es un error.
    assert client.delete(ruta, headers=headers).status_code == 204


def test_token_vencido_401(env):
    client, headers, TestSession = env
    agente_id = _crear_agente(client, headers)
    creado = _emitir_token(client, headers, agente_id, dias_validez=1).json()
    with TestSession() as s:
        fila = s.get(TokenAgente, uuid.UUID(creado["id"]))
        fila.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        s.commit()

    assert client.get("/api/v1/users/me", headers=_bearer(creado["token"])).status_code == 401


def test_token_de_usuario_apagado_401(env):
    client, headers, _ = env
    agente_id = _crear_agente(client, headers)
    raw = _emitir_token(client, headers, agente_id).json()["token"]

    assert (
        client.patch(
            f"/api/v1/users/{agente_id}", headers=headers, json={"activo": False}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/users/me", headers=_bearer(raw)).status_code == 401


def test_usuario_humano_no_puede_tener_token(env):
    """Una credencial de larga vida sin lockout ni rotación es justo lo que
    el login evita para una persona."""
    client, headers, TestSession = env
    with TestSession() as s:
        humano_id = s.scalar(select(Usuario.id).where(Usuario.username == "admin"))

    r = _emitir_token(client, headers, humano_id)
    assert r.status_code == 409
    assert "agente_ia" in r.json()["detail"]


def test_token_inventado_401(env):
    client, _, _ = env
    assert client.get("/api/v1/users/me", headers=_bearer("prv_no-existe")).status_code == 401


def test_registra_el_ultimo_uso(env):
    client, headers, _ = env
    agente_id = _crear_agente(client, headers)
    creado = _emitir_token(client, headers, agente_id).json()
    assert creado["ultimo_uso_en"] is None

    client.get("/api/v1/users/me", headers=_bearer(creado["token"]))

    listado = client.get(f"/api/v1/users/{agente_id}/tokens", headers=headers).json()
    assert listado[0]["ultimo_uso_en"] is not None


def test_emitir_token_exige_permiso(env):
    client, headers, TestSession = env
    agente_id = _crear_agente(client, headers)
    client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "cajera", "pin": "123456", "tipo": "humano"},
    )
    with TestSession() as s:
        ajeno = auth_headers(s, "cajera")

    assert _emitir_token(client, ajeno, agente_id).status_code == 403
