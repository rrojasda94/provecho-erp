"""Tests del slice auth/RBAC: login, lockout, rotación de refresh, /me, RBAC.

Usa SQLite en memoria (StaticPool = una sola conexión compartida) y sobreescribe
la dependencia get_db.
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
from src.modules.users.domain import rules


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


def _login(client, username="admin", pin="123456"):
    return client.post("/api/v1/auth/login", json={"username": username, "pin": pin})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_ok_devuelve_tokens(client):
    r = _login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_pin_incorrecto_401(client):
    r = _login(client, pin="000000")
    assert r.status_code == 401


def test_login_usuario_inexistente_401(client):
    r = _login(client, username="fantasma")
    assert r.status_code == 401


def test_lockout_tras_max_intentos(client):
    for _i in range(rules.MAX_INTENTOS_FALLIDOS):
        assert _login(client, pin="000000").status_code in (401, 423)
    # Siguiente intento (incluso con PIN correcto) → bloqueado.
    r = _login(client, pin="123456")
    assert r.status_code == 423


def test_me_devuelve_roles_y_permisos(client):
    token = _login(client).json()["access_token"]
    r = client.get("/api/v1/users/me", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert "admin" in body["roles"]
    assert "*" in body["permisos"]


def test_me_sin_token_401(client):
    assert client.get("/api/v1/users/me").status_code == 401  # sin credenciales


def test_refresh_rota_y_reuso_revoca_cadena(client):
    tokens = _login(client).json()
    old = tokens["refresh_token"]

    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert r1.status_code == 200
    nuevo = r1.json()["refresh_token"]
    assert nuevo != old

    # Reusar el viejo (ya rotado) → 401 y revoca toda la sesión.
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert r2.status_code == 401

    # El nuevo también quedó revocado por la detección de reuso.
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": nuevo})
    assert r3.status_code == 401


def test_logout_revoca_refresh(client):
    tokens = _login(client).json()
    assert client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    ).status_code == 204
    r = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r.status_code == 401


def test_rbac_deny_por_defecto_403(client):
    # admin crea un usuario sin roles.
    admin_token = _login(client).json()["access_token"]
    r = client.post(
        "/api/v1/users",
        headers=_auth(admin_token),
        json={"username": "cajero_test", "pin": "654321"},
    )
    assert r.status_code == 201

    # Ese usuario, sin permisos, no puede usar endpoints admin.
    token = _login(client, "cajero_test", "654321").json()["access_token"]
    assert client.get("/api/v1/users", headers=_auth(token)).status_code == 403
    # Pero sí puede ver su propio perfil.
    assert client.get("/api/v1/users/me", headers=_auth(token)).status_code == 200


def test_crear_usuario_pin_invalido_422(client):
    admin_token = _login(client).json()["access_token"]
    r = client.post(
        "/api/v1/users",
        headers=_auth(admin_token),
        json={"username": "malpin", "pin": "12ab"},
    )
    assert r.status_code == 422


def test_roles_de_un_usuario_traen_su_id_para_poder_quitarlos(client):
    """La pantalla de Usuarios necesita el id del rol, no solo su nombre:
    el token trae nombres y con eso no se puede desasignar nada."""
    admin_token = _login(client).json()["access_token"]
    h = _auth(admin_token)
    usuario_id = client.post(
        "/api/v1/users", headers=h, json={"username": "mozo1", "pin": "654321"}
    ).json()["id"]
    assert client.get(f"/api/v1/users/{usuario_id}/roles", headers=h).json() == []

    roles = client.get("/api/v1/roles", headers=h).json()
    cajero = next(r for r in roles if r["nombre"] == "cajero")
    client.post(
        f"/api/v1/users/{usuario_id}/roles", headers=h, json={"rol_id": cajero["id"]}
    )

    asignados = client.get(f"/api/v1/users/{usuario_id}/roles", headers=h).json()
    assert [r["nombre"] for r in asignados] == ["cajero"]
    assert asignados[0]["id"] == cajero["id"]

    client.delete(f"/api/v1/users/{usuario_id}/roles/{cajero['id']}", headers=h)
    assert client.get(f"/api/v1/users/{usuario_id}/roles", headers=h).json() == []


def test_los_permisos_de_un_rol_se_pueden_consultar(client):
    """Asignar un rol a ciegas —sin ver qué habilita— es justo el error que
    este endpoint evita."""
    admin_token = _login(client).json()["access_token"]
    h = _auth(admin_token)
    roles = client.get("/api/v1/roles", headers=h).json()
    cajero = next(r for r in roles if r["nombre"] == "cajero")

    r = client.get(f"/api/v1/roles/{cajero['id']}/permisos", headers=h)
    assert r.status_code == 200
    codigos = [p["codigo"] for p in r.json()]
    assert "sales.cobrar" in codigos
    assert codigos == sorted(codigos)


def test_roles_de_un_usuario_inexistente_404(client):
    admin_token = _login(client).json()["access_token"]
    r = client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000000/roles",
        headers=_auth(admin_token),
    )
    assert r.status_code == 404


# --- Desbloqueo de pantalla del PDV (RN-POS-014) -------------------------------
def test_verificar_pin_confirma_identidad_sin_rotar_la_sesion(client):
    tokens = _login(client).json()
    h = _auth(tokens["access_token"])
    r = client.post("/api/v1/auth/verificar-pin", headers=h, json={"pin": "123456"})
    assert r.status_code == 204
    # No emite tokens: el PDV se desbloquea con la MISMA sesión, así que el
    # borrador y las cookies siguen donde estaban.
    assert r.content == b""
    assert client.get("/api/v1/users/me", headers=h).status_code == 200


def test_verificar_pin_incorrecto_401(client):
    h = _auth(_login(client).json()["access_token"])
    r = client.post("/api/v1/auth/verificar-pin", headers=h, json={"pin": "999999"})
    assert r.status_code == 401


def test_verificar_pin_sin_sesion_401(client):
    assert client.post(
        "/api/v1/auth/verificar-pin", json={"pin": "123456"}
    ).status_code == 401


def test_verificar_pin_cuenta_contra_el_mismo_lockout_que_el_login(client):
    h = _auth(_login(client).json()["access_token"])
    for _i in range(rules.MAX_INTENTOS_FALLIDOS):
        assert client.post(
            "/api/v1/auth/verificar-pin", headers=h, json={"pin": "000000"}
        ).status_code in (401, 423)
    # Un contador propio habría dejado probar PINes sin agotar los del login.
    assert _login(client).status_code == 423


# --- El claim `sucursales` es una lista estable ------------------------------
def test_las_sucursales_del_token_van_ordenadas_y_sin_las_borradas(client):
    """Esa lista **es** el claim del token, y hay pantallas que toman la
    primera: el PDV abría "su" sucursal por el índice 0.

    Sin `ORDER BY` el orden lo decidía Postgres y podía cambiar entre dos
    emisiones del mismo usuario — la caja de una sucursal terminaba creando
    los pedidos en la otra. Y sin filtrar `deleted_at`, una sucursal borrada
    seguía viajando en el token: `Tenant.exigir_sucursal` la dejaba pasar y
    el listado de ventas devolvía vacío en vez de negar el acceso.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from src.modules.users.infrastructure.models import (
        Empresa,
        Marca,
        Sucursal,
        Usuario,
        UsuarioSucursal,
    )
    from src.modules.users.infrastructure.repositories import UsuarioRepo

    session = next(client.app.dependency_overrides[get_db]())
    empresa = session.scalar(select(Empresa))
    marca = session.scalar(select(Marca))
    admin = session.scalar(select(Usuario).where(Usuario.username == "admin"))
    creadas = []
    # A propósito fuera de orden alfabético al insertar: si el repositorio no
    # ordena, el test pasa por casualidad con el orden de inserción.
    for nombre in ("Zorritos", "Amazonas", "Borrada"):
        s = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre=nombre,
            direccion="Jr. X 1", tenencia="alquilada",
        )
        session.add(s)
        session.flush()
        session.add(UsuarioSucursal(usuario_id=admin.id, sucursal_id=s.id))
        creadas.append(s)
    creadas[-1].deleted_at = datetime.now(UTC)
    session.commit()

    nombres = [
        session.get(Sucursal, sid).nombre
        for sid in UsuarioRepo(session).sucursal_ids(admin.id)
    ]
    assert "Borrada" not in nombres
    assert {"Amazonas", "Zorritos"} <= set(nombres)
    assert nombres == sorted(nombres)
