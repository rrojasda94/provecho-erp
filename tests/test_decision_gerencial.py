"""Acta de decisión gerencial (RN-GER-002): una decisión verbal no tiene
validez operativa, así que toda aprobación/directiva escalada deja una fila.

La referencia es polimórfica sin FK a propósito (ver el modelo): la decisión
aplica a una OC, una campaña o una sanción, y ningún módulo gana una FK
hacia `shared`.
"""

import uuid
from datetime import date

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
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
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
        # Sin sucursal el JWT sale sin `empresa_id` y todo responde 403 (ADR-004).
        s.add(
            UsuarioSucursal(
                usuario_id=usuario.id, sucursal_id=s.scalar(select(Sucursal)).id
            )
        )
        s.commit()


def _cuerpo(**overrides):
    body = {
        "tipo": "aprobacion",
        "referencia_tipo": "orden_compra",
        "referencia_id": str(uuid.uuid4()),
        "sustento": "El monto supera el umbral y la obra no puede parar.",
        "resultado": "aprobado",
        "fecha": str(date(2026, 8, 3)),
    }
    body.update(overrides)
    return body


def _registrar(client, h, **overrides):
    return client.post(
        "/api/v1/decisiones-gerenciales", headers=h, json=_cuerpo(**overrides)
    )


def test_registrar_decision(env):
    client, _, _ = env
    h = _token(client)
    r = _registrar(client, h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tipo"] == "aprobacion"
    assert body["resultado"] == "aprobado"
    assert body["referencia_tipo"] == "orden_compra"


def test_decidido_por_sale_del_token_no_del_cuerpo(env):
    """Atribuirle la decisión a otro gerente invalidaría el acta entera."""
    client, _, TestSession = env
    h = _token(client)
    # `decidido_por_id` no está en el schema: mandarlo no cambia nada.
    otro = uuid.uuid4()
    r = client.post(
        "/api/v1/decisiones-gerenciales",
        headers=h,
        json=_cuerpo() | {"decidido_por_id": str(otro)},
    )
    assert r.status_code == 201
    with TestSession() as s:
        admin_id = s.scalar(select(Usuario.id).where(Usuario.username == "admin"))
    assert r.json()["decidido_por_id"] == str(admin_id)


def test_aprobado_con_condiciones_exige_condiciones(env):
    client, _, _ = env
    h = _token(client)
    r = _registrar(client, h, resultado="aprobado_con_condiciones")
    assert r.status_code == 409
    ok = _registrar(
        client, h,
        resultado="aprobado_con_condiciones",
        condiciones="Solo si el proveedor entrega antes del 15.",
    )
    assert ok.status_code == 201


def test_sustento_vacio_se_rechaza(env):
    """Un acta sin sustento no explica nada (RN-GER-002)."""
    client, _, _ = env
    h = _token(client)
    assert _registrar(client, h, sustento="   ").status_code == 409


def test_tipo_y_resultado_invalidos_mueren_en_el_borde(env):
    client, _, _ = env
    h = _token(client)
    assert _registrar(client, h, tipo="inventado").status_code == 422
    assert _registrar(client, h, resultado="quizas").status_code == 422


def test_area_ejecutora_desconocida_se_rechaza(env):
    client, _, _ = env
    h = _token(client)
    # `Literal[MODULOS]` la corta en el borde: "contabilidad" es el nombre del
    # área de negocio, no el del módulo de código (`accounting`).
    assert _registrar(client, h, ejecuta_area="contabilidad").status_code == 422
    assert _registrar(client, h, ejecuta_area="accounting").status_code == 201


def test_listar_filtra_por_referencia(env):
    """El acceso real: "qué decidió Gerencia sobre esto"."""
    client, _, _ = env
    h = _token(client)
    ref = str(uuid.uuid4())
    _registrar(client, h, referencia_id=ref)
    _registrar(client, h, referencia_id=str(uuid.uuid4()))

    r = client.get(
        "/api/v1/decisiones-gerenciales",
        headers=h,
        params={"referencia_tipo": "orden_compra", "referencia_id": ref},
    )
    assert r.status_code == 200
    assert [d["referencia_id"] for d in r.json()] == [ref]


def test_ver_decision_por_id(env):
    client, _, _ = env
    h = _token(client)
    creada = _registrar(client, h).json()
    r = client.get(f"/api/v1/decisiones-gerenciales/{creada['id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == creada["id"]


def test_decision_inexistente_404(env):
    client, _, _ = env
    h = _token(client)
    r = client.get(f"/api/v1/decisiones-gerenciales/{uuid.uuid4()}", headers=h)
    assert r.status_code == 404


def test_leer_no_habilita_decidir(env):
    """El área ejecutora (RN-GER-005) ve el acta pero no la firma."""
    client, _, TestSession = env
    _crear_usuario_con_permisos(TestSession, "ejecutor", ["gerencia.leer_decisiones"])
    h = _token(client, "ejecutor", "222222")
    assert client.get("/api/v1/decisiones-gerenciales", headers=h).status_code == 200
    assert _registrar(client, h).status_code == 403


def test_decidir_exige_su_permiso(env):
    client, _, TestSession = env
    _crear_usuario_con_permisos(TestSession, "sinpermiso", ["sales.leer"])
    h = _token(client, "sinpermiso", "222222")
    assert _registrar(client, h).status_code == 403
    assert client.get("/api/v1/decisiones-gerenciales", headers=h).status_code == 403


def test_gerente_con_gerencia_decidir_puede_firmar(env):
    client, _, TestSession = env
    _crear_usuario_con_permisos(TestSession, "gerente", ["gerencia.decidir"])
    h = _token(client, "gerente", "222222")
    assert _registrar(client, h).status_code == 201
