"""Tests del CRUD de `persona` (party model) y su lock optimista (`version`).

Mismo fixture/estilo que test_users_auth.py: SQLite en memoria + StaticPool.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401  (puebla Base.metadata)
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    with TestSession() as s:
        seed(s)

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


def _admin_auth(client):
    token = client.post(
        "/api/v1/auth/login", json={"username": "admin", "pin": "123456"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _crear_persona(client, headers, numero_documento="12345678"):
    return client.post(
        "/api/v1/personas",
        headers=headers,
        json={
            "nombres": "Ana",
            "apellidos": "Torres",
            "tipo_documento": "dni",
            "numero_documento": numero_documento,
        },
    )


def test_crear_persona_ok_201(client):
    r = _crear_persona(client, _admin_auth(client))
    assert r.status_code == 201
    body = r.json()
    assert body["numero_documento"] == "12345678"
    assert body["version"] == 1


def test_crear_persona_documento_duplicado_409(client):
    headers = _admin_auth(client)
    assert _crear_persona(client, headers).status_code == 201
    assert _crear_persona(client, headers).status_code == 409


def test_obtener_persona_404(client):
    headers = _admin_auth(client)
    r = client.get(
        "/api/v1/personas/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert r.status_code == 404


def test_listar_personas(client):
    headers = _admin_auth(client)
    _crear_persona(client, headers)
    r = client.get("/api/v1/personas", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_editar_persona_version_correcta_incrementa_version(client):
    headers = _admin_auth(client)
    persona = _crear_persona(client, headers).json()

    r = client.patch(
        f"/api/v1/personas/{persona['id']}",
        headers=headers,
        json={"version": persona["version"], "telefono": "999111222"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["telefono"] == "999111222"
    assert body["version"] == 2


def test_editar_persona_version_desactualizada_409(client):
    """Dos ediciones concurrentes con la misma version de partida: la
    primera gana, la segunda (version ya vieja) choca con 409 — no se
    pisan en silencio."""
    headers = _admin_auth(client)
    persona = _crear_persona(client, headers).json()

    r1 = client.patch(
        f"/api/v1/personas/{persona['id']}",
        headers=headers,
        json={"version": persona["version"], "telefono": "111111111"},
    )
    assert r1.status_code == 200

    r2 = client.patch(
        f"/api/v1/personas/{persona['id']}",
        headers=headers,
        json={"version": persona["version"], "telefono": "222222222"},
    )
    assert r2.status_code == 409


# --- Derecho de cancelación: anonimización (Ley 29733, ADR-011) -------------
def test_anonimizar_persona_borra_los_campos_identificables(client) -> None:
    headers = _admin_auth(client)
    persona = _crear_persona(client, headers).json()

    r = client.post(
        f"/api/v1/personas/{persona['id']}/anonimizar",
        headers=headers,
        json={"motivo": "solicitud ARCO del titular"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["nombres"] == "ANONIMIZADO"
    assert body["apellidos"] == "ANONIMIZADO"
    assert body["numero_documento"] != persona["numero_documento"]
    assert body["numero_documento"].startswith("ANON")
    assert body["domicilio"] is None
    assert body["telefono"] is None
    assert body["email"] is None
    assert body["anonimizado_at"] is not None


def test_anonimizar_persona_dos_veces_da_409(client) -> None:
    headers = _admin_auth(client)
    persona = _crear_persona(client, headers).json()
    primera = client.post(
        f"/api/v1/personas/{persona['id']}/anonimizar",
        headers=headers,
        json={"motivo": "solicitud ARCO"},
    )
    assert primera.status_code == 200

    segunda = client.post(
        f"/api/v1/personas/{persona['id']}/anonimizar",
        headers=headers,
        json={"motivo": "reintento"},
    )
    assert segunda.status_code == 409


def test_anonimizar_persona_inexistente_da_404(client) -> None:
    headers = _admin_auth(client)
    r = client.post(
        "/api/v1/personas/00000000-0000-0000-0000-000000000000/anonimizar",
        headers=headers,
        json={"motivo": "solicitud ARCO"},
    )
    assert r.status_code == 404


def test_no_se_puede_rectificar_una_persona_ya_anonimizada(client) -> None:
    """Anonimizar y luego "corregir" un dato ya borrado no tiene sentido —
    RN-PER-007 lo bloquea con 409, no lo deja pisar en silencio."""
    headers = _admin_auth(client)
    persona = _crear_persona(client, headers).json()
    client.post(
        f"/api/v1/personas/{persona['id']}/anonimizar",
        headers=headers,
        json={"motivo": "solicitud ARCO"},
    )

    r = client.patch(
        f"/api/v1/personas/{persona['id']}",
        headers=headers,
        json={"version": persona["version"], "telefono": "999888777"},
    )
    assert r.status_code == 409


def test_anonimizar_no_permitido_sin_el_permiso_dedicado(client) -> None:
    """`users.gestionar` alcanza para CRUD normal de persona pero no para
    anonimizar — permiso separado a propósito, la acción es irreversible."""
    headers = _admin_auth(client)
    persona = _crear_persona(client, headers).json()

    # Rol con users.gestionar (CRUD normal) pero SIN personas.anonimizar.
    rol_id = client.post(
        "/api/v1/roles", headers=headers, json={"nombre": "solo_crud_personas"}
    ).json()["id"]
    permiso_id = next(
        p["id"]
        for p in client.get("/api/v1/permisos", headers=headers).json()
        if p["codigo"] == "users.gestionar"
    )
    client.post(
        f"/api/v1/roles/{rol_id}/permisos",
        headers=headers,
        json={"permiso_id": permiso_id},
    )
    usuario_id = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "crud_only", "pin": "654321", "tipo": "humano"},
    ).json()["id"]
    client.post(
        f"/api/v1/users/{usuario_id}/roles", headers=headers, json={"rol_id": rol_id}
    )

    token = client.post(
        "/api/v1/auth/login", json={"username": "crud_only", "pin": "654321"}
    ).json()["access_token"]
    headers_limitado = {"Authorization": f"Bearer {token}"}

    r = client.post(
        f"/api/v1/personas/{persona['id']}/anonimizar",
        headers=headers_limitado,
        json={"motivo": "solicitud ARCO"},
    )
    assert r.status_code == 403
