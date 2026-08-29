"""Guest tokens de Superset — `src/core/bi_router.py` (ADR-083 Fase D).

`guest_token` (el cliente HTTP real de `src/shared/integrations/superset/`)
se monkeypatchea: este archivo prueba el endpoint —permiso, whitelist,
traducción de errores—, no la integración HTTP con un Superset real (esa la
verificó a mano `docs/engineering/bi-superset.md` al ensayar la Fase C).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.bi_router as bi_router
import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.shared.integrations.superset.client import SupersetError

DASHBOARD_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _whitelist(monkeypatch):
    monkeypatch.setattr(settings, "bi_dashboards_embebibles", [DASHBOARD_ID])


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


def _headers(client: TestClient, username="admin", pin="123456") -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_sin_bi_acceder_403(env):
    headers = _headers(env, username="cajero1", pin="123456")
    r = env.get(f"/api/v1/bi/dashboards/{DASHBOARD_ID}/guest-token", headers=headers)
    assert r.status_code == 403


def test_dashboard_fuera_de_la_whitelist_404(env):
    headers = _headers(env)
    r = env.get(
        "/api/v1/bi/dashboards/22222222-2222-2222-2222-222222222222/guest-token",
        headers=headers,
    )
    assert r.status_code == 404


def test_token_emitido_200(env, monkeypatch):
    monkeypatch.setattr(bi_router, "guest_token", lambda *a, **k: "un-token-de-prueba")
    headers = _headers(env)
    r = env.get(f"/api/v1/bi/dashboards/{DASHBOARD_ID}/guest-token", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"token": "un-token-de-prueba"}


def test_superset_caido_502(env, monkeypatch):
    def _falla(*a, **k):
        raise SupersetError("Superset no responde")

    monkeypatch.setattr(bi_router, "guest_token", _falla)
    headers = _headers(env)
    r = env.get(f"/api/v1/bi/dashboards/{DASHBOARD_ID}/guest-token", headers=headers)
    assert r.status_code == 502
