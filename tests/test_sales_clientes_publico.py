"""Test del contrato público de lectura `sales.cliente` (GET /sales/clientes),
consumido por marketing/comercial para análisis — no requiere permiso
`sales.leer` (ese es sobre ventas), sino `sales.leer_clientes_externos`.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.sales.infrastructure.models import Cliente
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Grupo, Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        grupo = s.scalar(select(Grupo))
        cliente = Cliente(
            grupo_id=grupo.id, tipo="juridico", razon_social="Eventos SAC",
            contacto="eventos@example.com",
        )
        s.add(cliente)

        supervisor = Usuario(username="super1", pin_hash=hash_pin("222222"), tipo="humano")
        cajero = Usuario(username="cajero1", pin_hash=hash_pin("333333"), tipo="humano")
        s.add_all([supervisor, cajero])
        s.flush()
        rol_supervisor = s.scalar(select(Rol).where(Rol.nombre == "supervisor"))
        rol_cajero = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add_all([
            UsuarioRol(usuario_id=supervisor.id, rol_id=rol_supervisor.id),
            UsuarioRol(usuario_id=cajero.id, rol_id=rol_cajero.id),
        ])
        ids["grupo_id"] = str(grupo.id)
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
        yield c, ids


def _token(client, username, pin):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_supervisor_lee_clientes_para_analisis(env):
    client, ids = env
    headers = _token(client, "super1", "222222")
    r = client.get(f"/api/v1/sales/clientes?grupo_id={ids['grupo_id']}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["nombre"] == "Eventos SAC"


def test_cajero_sin_permiso_403(env):
    client, ids = env
    headers = _token(client, "cajero1", "333333")
    r = client.get(f"/api/v1/sales/clientes?grupo_id={ids['grupo_id']}", headers=headers)
    assert r.status_code == 403
