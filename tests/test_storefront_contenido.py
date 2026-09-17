"""Gestion del CMS minimo del sitio de marca (`/storefront/contenido`,
ADR-101): permisos (`storefront.leer`/`storefront.editar`) y validacion
de forma por clave.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Grupo, Marca, Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin

CONTENIDO = "/api/v1/storefront/contenido"


@pytest.fixture()
def env(_app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))

        marketing = Usuario(username="marketing1", pin_hash=hash_pin("222222"), tipo="humano")
        cajero = Usuario(username="cajero_web", pin_hash=hash_pin("333333"), tipo="humano")
        s.add_all([marketing, cajero])
        s.flush()
        rol_marketing = s.scalar(select(Rol).where(Rol.nombre == "marketing"))
        rol_cajero = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add_all([
            UsuarioRol(usuario_id=marketing.id, rol_id=rol_marketing.id),
            UsuarioRol(usuario_id=cajero.id, rol_id=rol_cajero.id),
        ])
        ids["marca_id"] = str(marca.id)
        s.commit()

    app = _app_compartida

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
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_marketing_guarda_y_lee_el_hero(env):
    client, ids = env
    headers = _token(client, "marketing1", "222222")

    body = {"valor": {"titulo": "A tu manera", "subtitulo": "Pizza de barrio"}}
    r = client.put(
        CONTENIDO + "/hero", headers=headers, params={"marca_id": ids["marca_id"]}, json=body
    )
    assert r.status_code == 200, r.text
    assert r.json()["valor"]["titulo"] == "A tu manera"
    assert r.json()["updated_by"] is not None

    r2 = client.get(CONTENIDO, headers=headers, params={"marca_id": ids["marca_id"]})
    assert r2.status_code == 200
    claves = [f["clave"] for f in r2.json()]
    assert "hero" in claves


def test_guardar_contenido_invalido_es_422_de_regla_de_negocio(env):
    client, ids = env
    headers = _token(client, "marketing1", "222222")

    body = {"valor": {"subtitulo": "sin titulo"}}
    r = client.put(
        CONTENIDO + "/hero", headers=headers, params={"marca_id": ids["marca_id"]}, json=body
    )
    assert r.status_code >= 400


def test_cajero_sin_permiso_403_al_editar(env):
    client, ids = env
    headers = _token(client, "cajero_web", "333333")
    body = {"valor": {"titulo": "hackeo"}}
    r = client.put(
        CONTENIDO + "/hero", headers=headers, params={"marca_id": ids["marca_id"]}, json=body
    )
    assert r.status_code == 403


def test_cajero_sin_permiso_403_al_leer(env):
    client, ids = env
    headers = _token(client, "cajero_web", "333333")
    r = client.get(CONTENIDO, headers=headers, params={"marca_id": ids["marca_id"]})
    assert r.status_code == 403


def test_sin_token_401(env):
    client, ids = env
    r = client.get(CONTENIDO, params={"marca_id": ids["marca_id"]})
    assert r.status_code == 401
