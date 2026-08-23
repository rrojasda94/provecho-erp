"""Preferencias de presentación del usuario (tema, tamaño de letra, paleta).

Viven en el perfil y no en el navegador (docs/product/ui-ux.md): en un local
la misma tablet la usan tres turnos y la misma persona salta de la caja a la
oficina. Estos tests fijan las dos propiedades que hacen que eso valga la
pena — que se persistan y que cada usuario solo toque las suyas.
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


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_me_trae_las_preferencias_por_defecto(client):
    r = client.get("/api/v1/users/me", headers=_auth(_token(client)))
    assert r.status_code == 200
    body = r.json()
    assert body["preferencia_tema"] == "claro"
    assert body["preferencia_paleta"] == "estandar"
    assert body["preferencia_tamano_fuente"] == "estandar"


def test_cambiar_una_preferencia_no_pisa_las_otras(client):
    # La barra superior cambia una sola a la vez: si el PATCH exigiera el
    # objeto completo, tocar el tema apagaría el modo daltónico de alguien.
    token = _token(client)
    client.patch(
        "/api/v1/users/me/preferencias",
        json={"paleta": "alto_contraste"},
        headers=_auth(token),
    )
    r = client.patch(
        "/api/v1/users/me/preferencias",
        json={"tamano_fuente": "muy_grande"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["preferencia_paleta"] == "alto_contraste"
    assert body["preferencia_tamano_fuente"] == "muy_grande"
    assert body["preferencia_tema"] == "claro"


def test_la_preferencia_sobrevive_a_la_sesion(client):
    # El punto entero de guardarlas en el perfil: volver a entrar —en esta
    # máquina o en la tablet del almacén— y encontrarlas puestas.
    client.patch(
        "/api/v1/users/me/preferencias",
        json={"tema": "oscuro"},
        headers=_auth(_token(client)),
    )
    r = client.get("/api/v1/users/me", headers=_auth(_token(client)))
    assert r.json()["preferencia_tema"] == "oscuro"


def test_valor_fuera_del_catalogo_se_rechaza(client):
    r = client.patch(
        "/api/v1/users/me/preferencias",
        json={"tamano_fuente": "gigante"},
        headers=_auth(_token(client)),
    )
    assert r.status_code == 422


def test_sin_credenciales_401(client):
    assert client.patch("/api/v1/users/me/preferencias", json={"tema": "oscuro"}).status_code == 401
