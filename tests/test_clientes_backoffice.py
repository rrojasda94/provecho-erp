"""Padrón de clientes desde el back-office: listar, paginar y corregir.

Distinto de `test_sales_clientes_publico.py`, que cubre el contrato de
lectura para análisis externo (`GET /sales/clientes`, otro permiso). Acá se
prueba lo que usa la pantalla de administración: `GET /clientes/listado` y
`PATCH /clientes/{id}`.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.sales.application import clientes as clientes_uc
from src.modules.sales.infrastructure.models import Cliente
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Persona,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin


@pytest.fixture()
def env(monkeypatch):
    # Sin esto el alta de un jurídico consulta SUNAT de verdad y la razón
    # social del test depende de la red.
    monkeypatch.setattr(
        clientes_uc, "razon_social_desde_ruc", lambda ruc, tecleada: tecleada
    )
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
        empresa = s.scalar(select(Empresa))

        juridico = Cliente(
            grupo_id=grupo.id, tipo="juridico",
            razon_social="Eventos SAC", ruc="20111111111",
            contacto="eventos@example.com",
        )
        persona = Persona(
            nombres="Ana", apellidos="Torres", tipo_documento="dni",
            numero_documento="10000001", telefono="987654321",
        )
        s.add_all([juridico, persona])
        s.flush()
        natural = Cliente(grupo_id=grupo.id, tipo="natural", persona_id=persona.id)
        s.add(natural)

        cajero = Usuario(username="cajero_test", pin_hash=hash_pin("333333"), tipo="humano")
        s.add(cajero)
        s.flush()
        s.add(UsuarioRol(
            usuario_id=cajero.id,
            rol_id=s.scalar(select(Rol).where(Rol.nombre == "cajero")).id,
        ))
        # Sin sucursal el JWT sale sin `empresa_id` y el grupo del cliente no
        # se puede derivar (ADR-004).
        s.add(UsuarioSucursal(
            usuario_id=cajero.id, sucursal_id=s.scalar(select(Sucursal)).id
        ))

        s.flush()
        ids.update(
            grupo_id=str(grupo.id), empresa_id=str(empresa.id),
            juridico_id=str(juridico.id), natural_id=str(natural.id),
            persona_id=str(persona.id),
        )
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
        yield c, ids, TestSession


def _token(client, username="cajero_test", pin="333333"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_listado_devuelve_el_padron_del_grupo_paginado(env):
    client, ids, _ = env
    r = client.get("/api/v1/sales/clientes/listado", headers=_token(client))
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] == 2
    nombres = {c["nombre"] for c in cuerpo["items"]}
    assert nombres == {"Eventos SAC", "Ana Torres"}


def test_listado_resuelve_el_nombre_del_natural_desde_su_persona(env):
    """RN-GEN-007: el nombre no se duplica en `cliente`. Si el listado no
    resolviera la persona, el natural saldría como '—'."""
    client, ids, _ = env
    r = client.get("/api/v1/sales/clientes/listado", headers=_token(client))
    natural = next(c for c in r.json()["items"] if c["tipo"] == "natural")
    assert natural["nombre"] == "Ana Torres"
    assert natural["telefono"] == "987654321"
    # La pantalla lo usa para mandar a corregir los datos donde de verdad viven.
    assert natural["persona_id"] == ids["persona_id"]


def test_listado_filtra_por_q_igual_que_la_caja(env):
    client, ids, _ = env
    h = _token(client)
    r = client.get("/api/v1/sales/clientes/listado?q=Torres", headers=h)
    assert [c["nombre"] for c in r.json()["items"]] == ["Ana Torres"]
    r = client.get("/api/v1/sales/clientes/listado?q=20111111111", headers=h)
    assert [c["nombre"] for c in r.json()["items"]] == ["Eventos SAC"]


def test_buscar_de_caja_sigue_funcionando_igual(env):
    """`buscar` pasó a apoyarse en `q_listado`: el contrato del PDV no cambia."""
    client, ids, _ = env
    r = client.get("/api/v1/sales/clientes/buscar?q=Eventos", headers=_token(client))
    assert r.status_code == 200
    assert [c["nombre"] for c in r.json()] == ["Eventos SAC"]


def test_editar_cliente_juridico_corrige_ruc_y_razon_social(env):
    client, ids, _ = env
    r = client.patch(
        f"/api/v1/sales/clientes/{ids['juridico_id']}",
        headers=_token(client),
        json={"razon_social": "Eventos del Norte SAC", "ruc": "20999999999"},
    )
    assert r.status_code == 200
    assert r.json()["ruc"] == "20999999999"
    assert r.json()["razon_social"] == "Eventos del Norte SAC"


def test_editar_cliente_natural_409(env):
    """Sus datos viven en `persona` (RN-GEN-007). La pantalla manda a
    Personas en vez de ofrecer campos que serían una segunda fuente."""
    client, ids, _ = env
    r = client.patch(
        f"/api/v1/sales/clientes/{ids['natural_id']}",
        headers=_token(client),
        json={"razon_social": "Ana Torres SAC"},
    )
    assert r.status_code == 409
    assert "persona" in r.json()["detail"].lower()


def test_editar_cliente_con_ruc_de_otro_409(env):
    client, ids, TestSession = env
    with TestSession() as s:
        otro = Cliente(
            grupo_id=s.scalar(select(Grupo)).id, tipo="juridico",
            razon_social="Catering SAC", ruc="20555555555",
        )
        s.add(otro)
        s.commit()

    r = client.patch(
        f"/api/v1/sales/clientes/{ids['juridico_id']}",
        headers=_token(client),
        json={"ruc": "20555555555"},
    )
    assert r.status_code == 409


def test_editar_cliente_de_otro_grupo_403(env):
    """El cliente es del grupo (RN-PTS-001) y el endpoint no lo validaba:
    con el id de otro grupo escribía igual (ADR-004)."""
    client, ids, TestSession = env
    with TestSession() as s:
        ajeno_grupo = Grupo(nombre="Otro grupo")
        s.add(ajeno_grupo)
        s.flush()
        ajeno = Cliente(
            grupo_id=ajeno_grupo.id, tipo="juridico",
            razon_social="Ajena SAC", ruc="20777777777",
        )
        s.add(ajeno)
        s.commit()
        ajeno_id = str(ajeno.id)

    r = client.patch(
        f"/api/v1/sales/clientes/{ajeno_id}",
        headers=_token(client),
        json={"razon_social": "Robada SAC"},
    )
    assert r.status_code == 403


def test_listado_sin_sesion_401(env):
    client, ids, _ = env
    assert client.get("/api/v1/sales/clientes/listado").status_code == 401
