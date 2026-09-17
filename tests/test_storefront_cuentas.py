"""Cuenta de cliente del sitio de marca (`/storefront/cuentas/*`, ADR-102):
registro/login/refresh/logout, Google (mockeado), direcciones, favoritos,
el enlace a `cliente` por evento y el aislamiento frente a las credenciales
del ERP.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.sales.application import listeners as sales_listeners
from src.modules.sales.infrastructure.models import ProductoComercial
from src.modules.storefront.application import listeners as storefront_listeners
from src.modules.storefront.infrastructure.models import StorefrontCuenta
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Grupo, Marca

CUENTAS = "/api/v1/storefront/cuentas"


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(sales_listeners, "session_factory", TestSession)
    monkeypatch.setattr(storefront_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
        producto = ProductoComercial(id_interno="P0000003", marca_id=marca.id, nombre="Pizza Fav")
        s.add(producto)
        s.flush()
        ids.update(marca_id=str(marca.id), producto_id=str(producto.id))
        s.commit()

    from src.config.settings import settings

    monkeypatch.setattr(settings, "storefront_marca_id", ids["marca_id"])

    app = _app_compartida

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c, ids, TestSession


def _registro_body(email="ana@example.com", numero_documento="45678912"):
    return {
        "email": email, "password": "clave-larga-123", "nombres": "Ana",
        "apellidos": "Torres", "tipo_documento": "dni",
        "numero_documento": numero_documento, "telefono": "987654321",
        "fecha_nacimiento": "1995-05-20", "direccion": "Jr. Los Pinos 123",
    }


def test_registro_devuelve_tokens_y_202(env):
    client, ids, _ = env
    r = client.post(f"{CUENTAS}/registro", json=_registro_body())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_registro_email_duplicado_es_409(env):
    client, ids, _ = env
    client.post(f"{CUENTAS}/registro", json=_registro_body())
    r = client.post(f"{CUENTAS}/registro", json=_registro_body(numero_documento="11223344"))
    assert r.status_code == 409


def test_registro_se_vincula_a_un_cliente_de_sales(env):
    client, ids, TestSession = env
    r = client.post(f"{CUENTAS}/registro", json=_registro_body())
    token = r.json()["access_token"]

    with TestSession() as s:
        cuenta = s.scalar(
            select(StorefrontCuenta).where(StorefrontCuenta.email == "ana@example.com")
        )
        assert cuenta is not None
        assert cuenta.cliente_id is not None

    perfil = client.get(f"{CUENTAS}/me", headers={"Authorization": f"Bearer {token}"})
    assert perfil.status_code == 200
    assert perfil.json()["nombres"] == "Ana"


def test_login_correcto(env):
    client, ids, _ = env
    client.post(f"{CUENTAS}/registro", json=_registro_body())
    r = client.post(
        f"{CUENTAS}/login", json={"email": "ana@example.com", "password": "clave-larga-123"}
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_clave_incorrecta_401(env):
    client, ids, _ = env
    client.post(f"{CUENTAS}/registro", json=_registro_body())
    r = client.post(f"{CUENTAS}/login", json={"email": "ana@example.com", "password": "otra-clave"})
    assert r.status_code == 401


def test_login_bloquea_tras_cinco_intentos(env):
    """La quinta clave errada YA bloquea (mismo umbral que `users`,
    `MAX_INTENTOS_FALLIDOS=5`): se sobregira a `range(6)` sin mirar cada
    respuesta, y se confirma el bloqueo con una clave CORRECTA después —
    si igual entra, el lockout no está funcionando."""
    client, ids, _ = env
    client.post(f"{CUENTAS}/registro", json=_registro_body())
    for _ in range(6):
        client.post(f"{CUENTAS}/login", json={"email": "ana@example.com", "password": "mal"})
    r = client.post(
        f"{CUENTAS}/login", json={"email": "ana@example.com", "password": "clave-larga-123"}
    )
    assert r.status_code == 423


def test_refresh_rota_y_el_token_viejo_revoca_la_sesion(env):
    client, ids, _ = env
    tokens = client.post(f"{CUENTAS}/registro", json=_registro_body()).json()

    r2 = client.post(f"{CUENTAS}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 200
    assert r2.json()["refresh_token"] != tokens["refresh_token"]

    reuso = client.post(f"{CUENTAS}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuso.status_code == 401

    tokens_nuevos = r2.json()
    tras_reuso = client.post(
        f"{CUENTAS}/refresh", json={"refresh_token": tokens_nuevos["refresh_token"]}
    )
    assert tras_reuso.status_code == 401  # la sesión entera quedó revocada


def test_logout_es_idempotente(env):
    client, ids, _ = env
    tokens = client.post(f"{CUENTAS}/registro", json=_registro_body()).json()
    cuerpo = {"refresh_token": tokens["refresh_token"]}
    assert client.post(f"{CUENTAS}/logout", json=cuerpo).status_code == 204
    assert client.post(f"{CUENTAS}/logout", json=cuerpo).status_code == 204
    assert client.post(f"{CUENTAS}/refresh", json=cuerpo).status_code == 401


def test_google_sin_configurar_es_401(env):
    client, ids, _ = env
    r = client.post(f"{CUENTAS}/google", json={"id_token": "cualquiera"})
    assert r.status_code == 401


def test_google_cuenta_nueva_exige_datos_y_luego_funciona(env, monkeypatch):
    from src.modules.storefront.application import auth as storefront_auth

    monkeypatch.setattr(
        storefront_auth,
        "verificar_id_token",
        lambda id_token: {
            "sub": "google-sub-1", "email": "bruno@example.com",
            "email_verified": True, "nombres": "Bruno", "apellidos": "Diaz",
        },
    )
    client, ids, _ = env

    incompleto = client.post(f"{CUENTAS}/google", json={"id_token": "x"})
    assert incompleto.status_code >= 400

    completo = client.post(
        f"{CUENTAS}/google",
        json={
            "id_token": "x", "tipo_documento": "dni", "numero_documento": "77778888",
            "telefono": "911222333", "fecha_nacimiento": "1990-01-01",
            "direccion": "Av. Central 500",
        },
    )
    assert completo.status_code == 200, completo.text

    otra_vez = client.post(f"{CUENTAS}/google", json={"id_token": "x"})
    assert otra_vez.status_code == 200


def test_direcciones_crud(env):
    client, ids, _ = env
    token = client.post(f"{CUENTAS}/registro", json=_registro_body()).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    listado = client.get(f"{CUENTAS}/me/direcciones", headers=headers)
    assert listado.status_code == 200
    assert len(listado.json()) == 1  # la del registro
    assert listado.json()[0]["predeterminada"] is True

    nueva = client.post(
        f"{CUENTAS}/me/direcciones", headers=headers,
        json={"etiqueta": "Trabajo", "direccion": "Jr. Comercio 45", "predeterminada": True},
    )
    assert nueva.status_code == 201
    nueva_id = nueva.json()["id"]

    listado2 = client.get(f"{CUENTAS}/me/direcciones", headers=headers).json()
    assert sum(1 for d in listado2 if d["predeterminada"]) == 1  # solo una a la vez

    borrado = client.delete(f"{CUENTAS}/me/direcciones/{nueva_id}", headers=headers)
    assert borrado.status_code == 204
    listado3 = client.get(f"{CUENTAS}/me/direcciones", headers=headers).json()
    assert nueva_id not in [d["id"] for d in listado3]


def test_favoritos_crud(env):
    client, ids, _ = env
    token = client.post(f"{CUENTAS}/registro", json=_registro_body()).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    agregar = client.post(
        f"{CUENTAS}/me/favoritos", headers=headers,
        json={"producto_comercial_id": ids["producto_id"]},
    )
    assert agregar.status_code == 201

    duplicado = client.post(
        f"{CUENTAS}/me/favoritos", headers=headers,
        json={"producto_comercial_id": ids["producto_id"]},
    )
    assert duplicado.status_code == 409

    listado = client.get(f"{CUENTAS}/me/favoritos", headers=headers)
    assert listado.json() == [ids["producto_id"]]

    quitar = client.delete(f"{CUENTAS}/me/favoritos/{ids['producto_id']}", headers=headers)
    assert quitar.status_code == 204
    assert client.get(f"{CUENTAS}/me/favoritos", headers=headers).json() == []


def test_favorito_de_producto_inexistente_404(env):
    client, ids, _ = env
    token = client.post(f"{CUENTAS}/registro", json=_registro_body()).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"{CUENTAS}/me/favoritos", headers=headers,
        json={"producto_comercial_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


def test_ultimo_pedido_sin_compras_es_null(env):
    client, ids, _ = env
    token = client.post(f"{CUENTAS}/registro", json=_registro_body()).json()["access_token"]
    r = client.get(f"{CUENTAS}/me/ultimo-pedido", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() is None


def test_sin_token_no_autoriza(env):
    client, ids, _ = env
    assert client.get(f"{CUENTAS}/me").status_code in (401, 403)


def test_token_de_cuenta_web_no_sirve_en_el_erp(env):
    """Aislamiento de credenciales (ADR-102): un token de storefront no
    decodifica contra el secreto del ERP — falla en la firma, no llega
    siquiera a mirar el `sub`."""
    client, ids, _ = env
    token = client.post(f"{CUENTAS}/registro", json=_registro_body()).json()["access_token"]
    r = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_del_erp_no_sirve_en_storefront(env):
    client, ids, _ = env
    login = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    token_erp = login.json()["access_token"]
    r = client.get(f"{CUENTAS}/me", headers={"Authorization": f"Bearer {token_erp}"})
    assert r.status_code == 401
