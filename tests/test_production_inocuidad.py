"""Tests del checklist de inocuidad de turno (RN-CDP-002/005): crear
checklist calcula `estado`, y sin uno `aprobado` vigente del día la cocina
rechaza crear orden y registrar consumo. Mismo patrón de fixture que
`test_production_planes.py`, sin checklist preseedeado: estos tests
ejercitan justamente esa regla.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.production.application import listeners as production_listeners
from src.modules.production.infrastructure.models import (
    ChecklistInocuidadTurno,
    OrdenProduccion,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa, Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin
from src.shared import fechas


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(listeners, "session_factory", TestSession)
    monkeypatch.setattr(production_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        almacen = Almacen(empresa_id=empresa.id, nombre="Producción", tipo="produccion")
        s.add_all([udm, almacen])
        s.flush()

        harina = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        masa = Articulo(
            empresa_id=empresa.id, id_interno="M001", nombre="Masa madre",
            unidad_medida_id=udm.id, tipo="subreceta", controla_lote=True,
        )
        s.add_all([harina, masa])
        s.flush()
        sku_harina = Sku(articulo_id=harina.id, codigo="SKU-HARINA")
        s.add(sku_harina)
        s.add(Sku(articulo_id=masa.id, codigo="SKU-MASA"))
        s.flush()

        receta = Receta(
            empresa_id=empresa.id,
            nombre="Masa madre (BOM)", rendimiento_cantidad=Decimal(10),
            rendimiento_unidad_medida_id=udm.id, articulo_id=masa.id,
        )
        s.add(receta)
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal(1)))
        s.flush()

        s.add(Stock(almacen_id=almacen.id, sku_id=sku_harina.id, cantidad=Decimal(1000)))

        jefe_cocina = Usuario(username="jefe1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(jefe_cocina)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "jefe_cocina"))
        s.add(UsuarioRol(usuario_id=jefe_cocina.id, rol_id=rol.id))

        ids.update(
            empresa_id=str(empresa.id), almacen_id=str(almacen.id),
            harina_id=str(harina.id), masa_id=str(masa.id),
        )
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
        yield c, ids, TestSession


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_checklist(
    client,
    headers,
    ids,
    *,
    turno="mañana",
    fecha=None,
    bioseguridad_ok=True,
    superficies_ok=True,
    limpieza_intermedia_ok=True,
    equipos_frio=None,
    plaga_indicio=False,
):
    return client.post("/api/v1/production/checklists", headers=headers, json={
        "almacen_id": ids["almacen_id"],
        "fecha": fecha or fechas.hoy().isoformat(),
        "turno": turno,
        "bioseguridad_ok": bioseguridad_ok,
        "superficies_ok": superficies_ok,
        "limpieza_intermedia_ok": limpieza_intermedia_ok,
        "equipos_frio": equipos_frio or [],
        "plaga_indicio": plaga_indicio,
    })


def _crear_orden(client, headers, ids, key="op-inocuidad-1"):
    return client.post("/api/v1/production/ordenes", headers=headers, json={
        "articulo_id": ids["masa_id"], "almacen_id": ids["almacen_id"],
        "cantidad_planeada": "10", "idempotency_key": key,
    })


def test_crear_checklist_todo_ok_queda_aprobado(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_checklist(client, h, ids)
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "aprobado"


def test_crear_checklist_duplicado_409(env):
    client, ids, _ = env
    h = _token(client)
    assert _crear_checklist(client, h, ids).status_code == 201
    r = _crear_checklist(client, h, ids)
    assert r.status_code == 409


def test_crear_checklist_equipo_fuera_rango_queda_bloqueado(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_checklist(
        client, h, ids,
        equipos_frio=[
            {"equipo": "Cámara 1", "temperatura_c": "8", "rango_min": "0", "rango_max": "4"},
        ],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "bloqueado"
    assert body["equipos_frio"][0]["dentro_rango"] is False


def test_crear_checklist_plaga_indicio_queda_bloqueado(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_checklist(client, h, ids, plaga_indicio=True)
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "bloqueado"


def test_crear_orden_sin_checklist_409_y_no_crea_nada(env):
    """RN-CDP-005: sin checklist aprobado del día, la cocina está bloqueada
    por defecto — no es que arranque habilitada."""
    client, ids, TestSession = env
    h = _token(client)
    r = _crear_orden(client, h, ids)
    assert r.status_code == 409

    with TestSession() as s:
        assert s.scalar(select(OrdenProduccion)) is None


def test_crear_orden_con_checklist_aprobado_ok(env):
    client, ids, _ = env
    h = _token(client)
    assert _crear_checklist(client, h, ids).status_code == 201
    r = _crear_orden(client, h, ids)
    assert r.status_code == 201, r.text


def test_crear_orden_con_checklist_bloqueado_409(env):
    client, ids, _ = env
    h = _token(client)
    assert _crear_checklist(client, h, ids, plaga_indicio=True).status_code == 201
    r = _crear_orden(client, h, ids)
    assert r.status_code == 409


def test_registrar_consumo_bloqueado_por_checklist_posterior_409(env):
    """El checklist vigente es el más reciente del día: uno nuevo que
    bloquea la cocina detiene el consumo de una orden ya abierta."""
    client, ids, TestSession = env
    h = _token(client)
    assert _crear_checklist(client, h, ids, turno="mañana").status_code == 201
    orden_id = _crear_orden(client, h, ids).json()["id"]

    tarde_id = _crear_checklist(
        client, h, ids, turno="tarde", plaga_indicio=True
    ).json()["id"]
    # `vigente_de` desempata por `created_at`: SQLite solo guarda resolución
    # de segundo entero, y en la vida real un turno de tarde se registra
    # bastante después del de mañana — se fuerza acá para no depender de
    # que el test tarde un segundo entero en correr.
    with TestSession() as s:
        checklist_tarde = s.get(ChecklistInocuidadTurno, uuid.UUID(tarde_id))
        checklist_tarde.created_at += timedelta(hours=1)
        s.commit()

    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["harina_id"], "cantidad": "10", "costo_unitario": "2"}],
        },
    )
    assert r.status_code == 409


def test_listar_checklists(env):
    client, ids, _ = env
    h = _token(client)
    _crear_checklist(client, h, ids)
    listado = client.get("/api/v1/production/checklists", headers=h).json()
    assert listado["total"] == 1


def test_verificar_inocuidad_sin_permiso_403(env):
    client, ids, TestSession = env
    with TestSession() as s:
        cajero = Usuario(username="cajero_inocuidad", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cajero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol.id))
        s.commit()

    h_cajero = _token(client, "cajero_inocuidad", "222222")
    assert _crear_checklist(client, h_cajero, ids).status_code == 403
