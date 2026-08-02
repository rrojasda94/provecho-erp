"""CRUD antes diferido (ADR-014 Addendum b): unidad_medida/categoria_udm
(inventory) y divisa (gerencia) — hasta ahora solo se editaban por seeder.
Además, `/personas/buscar`: lookup minimizado para otro módulo (RRHH,
proveedor natural) sin exigir `users.gestionar`.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Permiso,
    Persona,
    Rol,
    RolPermiso,
    Usuario,
    UsuarioRol,
)
from src.modules.users.infrastructure.security import hash_pin


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
        s.add(
            Persona(
                nombres="Ana", apellidos="Ruiz",
                tipo_documento="dni", numero_documento="10000001",
            )
        )
        s.commit()

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c, TestSession


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_usuario_con_permisos(TestSession, username, codigos):
    with TestSession() as s:
        rol = Rol(nombre=f"rol-{username}")
        s.add(rol)
        s.flush()
        for codigo in codigos:
            permiso_id = s.scalar(select(Permiso.id).where(Permiso.codigo == codigo))
            assert permiso_id is not None, f"permiso {codigo} no sembrado"
            s.add(RolPermiso(rol_id=rol.id, permiso_id=permiso_id))
        usuario = Usuario(username=username, pin_hash=hash_pin("222222"), tipo="humano")
        s.add(usuario)
        s.flush()
        s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
        s.commit()


# --- unidad_medida / categoria_udm -------------------------------------------
def test_crear_categoria_udm_y_unidad_medida(env):
    client, _ = env
    h = _token(client)

    cat = client.post(
        "/api/v1/inventory/categorias-udm", headers=h, json={"nombre": "Peso"}
    )
    assert cat.status_code == 201

    udm = client.post(
        "/api/v1/inventory/unidades-medida",
        headers=h,
        json={
            "categoria_udm_id": cat.json()["id"],
            "nombre": "Kilo",
            "ratio": "1",
            "decimales": 3,
        },
    )
    assert udm.status_code == 201
    assert udm.json()["decimales"] == 3

    listado = client.get("/api/v1/inventory/unidades-medida", headers=h).json()
    assert any(u["nombre"] == "Kilo" for u in listado)


def test_crear_unidad_medida_duplicada_409(env):
    client, _ = env
    h = _token(client)
    cat_id = client.post(
        "/api/v1/inventory/categorias-udm", headers=h, json={"nombre": "Volumen"}
    ).json()["id"]
    body = {"categoria_udm_id": cat_id, "nombre": "Litro", "ratio": "1", "decimales": 3}
    assert client.post("/api/v1/inventory/unidades-medida", headers=h, json=body).status_code == 201
    assert client.post("/api/v1/inventory/unidades-medida", headers=h, json=body).status_code == 409


def test_crear_unidad_medida_sin_categoria_404(env):
    client, _ = env
    h = _token(client)
    body = {
        "categoria_udm_id": "00000000-0000-0000-0000-000000000000",
        "nombre": "Kilo",
        "ratio": "1",
        "decimales": 3,
    }
    assert client.post("/api/v1/inventory/unidades-medida", headers=h, json=body).status_code == 404


def test_editar_unidad_medida_decimales(env):
    """RN-GER-010: los decimales de una UdM se corrigen sin recrearla."""
    client, _ = env
    h = _token(client)
    cat_id = client.post(
        "/api/v1/inventory/categorias-udm", headers=h, json={"nombre": "Unidades"}
    ).json()["id"]
    udm_id = client.post(
        "/api/v1/inventory/unidades-medida",
        headers=h,
        json={"categoria_udm_id": cat_id, "nombre": "Unidad", "ratio": "1", "decimales": 3},
    ).json()["id"]

    r = client.patch(
        f"/api/v1/inventory/unidades-medida/{udm_id}", headers=h, json={"decimales": 0}
    )
    assert r.status_code == 200
    assert r.json()["decimales"] == 0


def test_gestionar_catalogo_udm_requiere_permiso(env):
    client, TestSession = env
    h_admin = _token(client)
    _crear_usuario_con_permisos(TestSession, "lector1", ["inventory.leer"])
    h = _token(client, "lector1", "222222")

    r = client.post(
        "/api/v1/inventory/categorias-udm", headers=h, json={"nombre": "Peso"}
    )
    assert r.status_code == 403
    assert client.get("/api/v1/inventory/unidades-medida", headers=h).status_code == 200
    assert client.get("/api/v1/inventory/unidades-medida", headers=h_admin).status_code == 200


# --- divisa -------------------------------------------------------------------
def test_crear_y_editar_divisa(env):
    client, _ = env
    h = _token(client)

    r = client.post(
        "/api/v1/divisas",
        headers=h,
        json={"codigo": "USD", "nombre": "Dólar", "simbolo": "$", "decimales": 2},
    )
    assert r.status_code == 201
    divisa_id = r.json()["id"]

    listado = client.get("/api/v1/divisas", headers=h).json()
    assert any(d["codigo"] == "USD" for d in listado)

    editado = client.patch(
        f"/api/v1/divisas/{divisa_id}", headers=h, json={"decimales": 0}
    )
    assert editado.status_code == 200
    assert editado.json()["decimales"] == 0


def test_crear_divisa_duplicada_409(env):
    client, _ = env
    h = _token(client)
    assert (
        client.post(
            "/api/v1/divisas", headers=h,
            json={"codigo": "PEN", "nombre": "Sol peruano 2", "simbolo": "S/", "decimales": 2},
        ).status_code
        == 409
    )  # PEN ya viene del seeder


def test_divisas_lectura_abierta_escritura_gobernada(env):
    client, TestSession = env
    h_admin = _token(client)
    _crear_usuario_con_permisos(TestSession, "cualquiera", ["inventory.leer"])
    h = _token(client, "cualquiera", "222222")

    # Cualquier autenticado lee (necesario para declarar montos, RN-GER-010).
    assert client.get("/api/v1/divisas", headers=h).status_code == 200
    # Pero no gobierna la moneda: eso es de Gerencia.
    assert (
        client.post(
            "/api/v1/divisas", headers=h,
            json={"codigo": "EUR", "nombre": "Euro", "simbolo": "€", "decimales": 2},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/divisas", headers=h_admin,
            json={"codigo": "EUR", "nombre": "Euro", "simbolo": "€", "decimales": 2},
        ).status_code
        == 201
    )


# --- /personas/buscar ---------------------------------------------------------
def test_buscar_personas_devuelve_solo_campos_minimos(env):
    client, _ = env
    h = _token(client)
    r = client.get("/api/v1/personas/buscar?q=Ana", headers=h)
    assert r.status_code == 200
    fila = r.json()[0]
    assert set(fila) == {"id", "nombres", "apellidos", "numero_documento"}
    assert "telefono" not in fila and "domicilio" not in fila


def test_buscar_personas_con_personas_leer_sin_gestionar(env):
    """Un rol RRHH/Compras puro (sin `users.gestionar`) sí puede buscar."""
    client, TestSession = env
    _crear_usuario_con_permisos(TestSession, "rrhh1", ["personas.leer"])
    h = _token(client, "rrhh1", "222222")

    assert client.get("/api/v1/personas/buscar?q=Ana", headers=h).status_code == 200
    # Pero la ficha completa (con PII) sigue exigiendo `users.gestionar`.
    assert client.get("/api/v1/personas", headers=h).status_code == 403


def test_buscar_personas_sin_ningun_permiso_403(env):
    client, TestSession = env
    _crear_usuario_con_permisos(TestSession, "nadie", ["inventory.leer"])
    h = _token(client, "nadie", "222222")
    assert client.get("/api/v1/personas/buscar", headers=h).status_code == 403
