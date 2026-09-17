"""Fotos de catalogo del sitio de marca (`/storefront/fotos/*`, ADR-101):
presign a S3, registro, listado y borrado. Mismo patron que
`test_assets.py::test_presign_adjunto_y_registro_completo`.
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.infrastructure.models import Articulo, CategoriaUdm, UnidadMedida
from src.modules.sales.infrastructure.models import ProductoComercial
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Empresa, Grupo, Marca

FOTOS = "/api/v1/storefront/fotos"


@pytest.fixture()
def env(_app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))

        producto = ProductoComercial(id_interno="P0000002", marca_id=marca.id, nombre="Pizza Foto")
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([producto, udm_cat])
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
        s.add(udm)
        s.flush()
        insumo = Articulo(
            empresa_id=empresa.id, id_interno="ART0002", nombre="Insumo Foto",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        s.add(insumo)
        s.flush()

        ids.update(producto_id=str(producto.id), insumo_id=str(insumo.id))
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


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_presign_sin_s3_configurado_409(env):
    client, ids = env
    h = _token(client)
    r = client.post(
        FOTOS + "/producto/" + ids["producto_id"] + "/presign-upload",
        headers=h,
        json={"nombre": "pizza.jpg", "mime_type": "image/jpeg"},
    )
    assert r.status_code == 409


def test_presignar_entidad_inexistente_404(env, monkeypatch):
    from src.shared.integrations.storage import s3

    monkeypatch.setattr(s3, "configurado", lambda: True)
    client, ids = env
    h = _token(client)
    import uuid

    r = client.post(
        FOTOS + "/producto/" + str(uuid.uuid4()) + "/presign-upload",
        headers=h,
        json={"nombre": "pizza.jpg", "mime_type": "image/jpeg"},
    )
    assert r.status_code == 404


def test_presign_registro_listado_y_borrado_completo(env, monkeypatch):
    from src.shared.integrations.storage import s3

    monkeypatch.setattr(s3, "configurado", lambda: True)
    monkeypatch.setattr(
        s3,
        "presigned_put_url",
        lambda clave, *, content_type, expira_segundos=300: (
            "https://s3.test/" + clave + "?firma=x"
        ),
    )
    monkeypatch.setattr(s3, "url_publica", lambda clave: "https://s3.test/" + clave)

    client, ids = env
    h = _token(client)

    presign = client.post(
        FOTOS + "/producto/" + ids["producto_id"] + "/presign-upload",
        headers=h,
        json={"nombre": "pizza.jpg", "mime_type": "image/jpeg"},
    )
    assert presign.status_code == 200, presign.text
    cuerpo = presign.json()
    assert cuerpo["upload_url"].startswith("https://s3.test/producto_comercial_foto/")
    assert cuerpo["url_storage"] == cuerpo["upload_url"].split("?")[0]

    registrar = client.post(
        FOTOS + "/producto/" + ids["producto_id"],
        headers=h,
        json={
            "nombre": "pizza.jpg", "mime_type": "image/jpeg", "tamano_bytes": 1024,
            "url_storage": cuerpo["url_storage"],
        },
    )
    assert registrar.status_code == 201, registrar.text
    archivo_id = registrar.json()["id"]

    listado = client.get(FOTOS + "/producto/" + ids["producto_id"], headers=h)
    assert listado.status_code == 200
    assert len(listado.json()) == 1
    assert listado.json()[0]["id"] == archivo_id

    borrar = client.delete(FOTOS + "/" + archivo_id, headers=h)
    assert borrar.status_code == 204

    listado2 = client.get(FOTOS + "/producto/" + ids["producto_id"], headers=h)
    assert listado2.json() == []


def test_mime_no_admitido_es_rechazado(env, monkeypatch):
    from src.shared.integrations.storage import s3

    monkeypatch.setattr(s3, "configurado", lambda: True)
    client, ids = env
    h = _token(client)
    r = client.post(
        FOTOS + "/ingrediente/" + ids["insumo_id"] + "/presign-upload",
        headers=h,
        json={"nombre": "receta.pdf", "mime_type": "application/pdf"},
    )
    assert r.status_code >= 400
