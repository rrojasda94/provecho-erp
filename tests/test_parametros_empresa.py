"""Parámetros operativos por empresa (ADR-014): el área propone desde su
módulo, Gerencia acepta / rechaza / modifica, y recién ahí el módulo lee el
valor nuevo.
"""

import uuid

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
    Empresa,
    Permiso,
    Rol,
    RolPermiso,
    Usuario,
    UsuarioRol,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared import parametros


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
        empresa_id = s.scalar(select(Empresa)).id
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
        yield c, str(empresa_id), TestSession


def _token(client: TestClient, username: str = "admin", pin: str = "123456") -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_usuario_con_permisos(client, h_admin, TestSession, username, codigos):
    """Usuario con un rol propio que solo tiene `codigos`. Directo a la BD:
    el CRUD administrativo por API no aporta nada a lo que se está probando."""
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


def _proponer(client, h, empresa_id, valor):
    return client.post(
        "/api/v1/parametros",
        headers=h,
        json={
            "empresa_id": empresa_id,
            "modulo": "inventory",
            "codigo": "margen_error_ajuste",
            "valor": valor,
            "motivo": "la operación pidió más holgura",
        },
    )


def _valor(TestSession, empresa_id):
    with TestSession() as s:
        return parametros.valor_vigente(
            s, uuid.UUID(empresa_id), "inventory", "margen_error_ajuste"
        )


def test_propuesta_no_surte_efecto_hasta_que_gerencia_aprueba(env):
    client, empresa_id, TestSession = env
    h = _token(client)

    r = _proponer(client, h, empresa_id, {"porcentaje": 3})
    assert r.status_code == 201
    assert r.json()["estado"] == "propuesto"
    # El módulo sigue sin ver nada: la propuesta no es un valor vigente.
    assert _valor(TestSession, empresa_id) is None

    pendientes = client.get("/api/v1/parametros?estado=propuesto", headers=h).json()
    assert [p["id"] for p in pendientes] == [r.json()["id"]]

    ok = client.post(
        f"/api/v1/parametros/{r.json()['id']}/aprobar", headers=h, json={}
    )
    assert ok.status_code == 200
    assert ok.json()["estado"] == "vigente"
    assert _valor(TestSession, empresa_id) == {"porcentaje": 3}


def test_gerencia_modifica_el_valor_al_aprobar(env):
    client, empresa_id, TestSession = env
    h = _token(client)
    propuesta_id = _proponer(client, h, empresa_id, {"porcentaje": 5}).json()["id"]

    r = client.post(
        f"/api/v1/parametros/{propuesta_id}/aprobar",
        headers=h,
        json={"valor": {"porcentaje": 3}},
    )
    assert r.status_code == 200
    assert _valor(TestSession, empresa_id) == {"porcentaje": 3}


def test_rechazo_deja_el_valor_anterior_intacto(env):
    client, empresa_id, TestSession = env
    h = _token(client)
    primero = _proponer(client, h, empresa_id, {"porcentaje": 2}).json()["id"]
    client.post(f"/api/v1/parametros/{primero}/aprobar", headers=h, json={})

    segundo = _proponer(client, h, empresa_id, {"porcentaje": 9}).json()["id"]
    r = client.post(
        f"/api/v1/parametros/{segundo}/rechazar",
        headers=h,
        json={"motivo_rechazo": "demasiada holgura"},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazado"
    assert _valor(TestSession, empresa_id) == {"porcentaje": 2}

    # Resolver dos veces la misma propuesta es conflicto, no doble efecto.
    assert (
        client.post(
            f"/api/v1/parametros/{segundo}/aprobar", headers=h, json={}
        ).status_code
        == 409
    )


def test_solo_se_proponen_parametros_del_propio_modulo(env):
    """Un permiso por módulo: quien solo puede proponer en `purchases` no
    toca los rangos salariales de `rrhh` (ADR-014 Addendum)."""
    client, empresa_id, TestSession = env
    h_admin = _token(client)
    _crear_usuario_con_permisos(
        client, h_admin, TestSession, "compras1", ["purchases.proponer_parametro"]
    )
    h = _token(client, "compras1", "222222")

    propio = client.post(
        "/api/v1/parametros",
        headers=h,
        json={
            "empresa_id": empresa_id,
            "modulo": "purchases",
            "codigo": "oc_umbral",
            "valor": {"monto": "5000", "divisa": "PEN"},
        },
    )
    assert propio.status_code == 201

    ajeno = client.post(
        "/api/v1/parametros",
        headers=h,
        json={
            "empresa_id": empresa_id,
            "modulo": "rrhh",
            "codigo": "rango_salarial_cocinero",
            "valor": {"minimo": 1, "maximo": 2, "divisa": "PEN"},
        },
    )
    assert ajeno.status_code == 403

    # Un módulo inventado muere en el borde, no llega al chequeo de permiso.
    inexistente = client.post(
        "/api/v1/parametros",
        headers=h,
        json={
            "empresa_id": empresa_id,
            "modulo": "contabilidad",
            "codigo": "plazo_envio_comprobante",
            "valor": {"dias": 5},
        },
    )
    assert inexistente.status_code == 422

    # Aprobar sigue siendo de Gerencia, no de quien propone.
    assert (
        client.post(
            f"/api/v1/parametros/{propio.json()['id']}/aprobar", headers=h, json={}
        ).status_code
        == 403
    )


def test_listar_sin_filtro_de_modulo_exige_permiso_de_gerencia(env):
    """Los rangos salariales de RRHH no son de lectura general: sin `?modulo`
    hace falta el permiso de Gerencia."""
    client, empresa_id, TestSession = env
    h_admin = _token(client)
    _crear_usuario_con_permisos(
        client, h_admin, TestSession, "compras2", ["purchases.proponer_parametro"]
    )
    h = _token(client, "compras2", "222222")

    assert client.get("/api/v1/parametros", headers=h).status_code == 403
    assert client.get("/api/v1/parametros?modulo=purchases", headers=h).status_code == 200
    assert client.get("/api/v1/parametros?modulo=rrhh", headers=h).status_code == 403


def test_aprobar_reemplaza_el_vigente_anterior(env):
    client, empresa_id, TestSession = env
    h = _token(client)
    primero = _proponer(client, h, empresa_id, {"porcentaje": 2}).json()["id"]
    client.post(f"/api/v1/parametros/{primero}/aprobar", headers=h, json={})
    segundo = _proponer(client, h, empresa_id, {"porcentaje": 4}).json()["id"]
    client.post(f"/api/v1/parametros/{segundo}/aprobar", headers=h, json={})

    assert _valor(TestSession, empresa_id) == {"porcentaje": 4}
    estados = {
        p["id"]: p["estado"]
        for p in client.get("/api/v1/parametros", headers=h).json()
    }
    assert estados[primero] == "reemplazado"
    assert estados[segundo] == "vigente"
