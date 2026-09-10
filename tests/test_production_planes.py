"""Tests del plan de producción: crear → agregar órdenes → iniciar
(reserva insumos) → cerrar (libera lo no consumido). Mismo patrón de
fixture que `test_production.py`.
"""

import uuid
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
    ReservaStock,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.production.application import listeners as production_listeners
from src.modules.production.infrastructure.models import PlanProduccion
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa, Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin


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
            harina_id=str(harina.id), masa_id=str(masa.id), sku_harina_id=str(sku_harina.id),
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


def _crear_plan(client, headers, ids, turno="mañana", linea="Panadería", fecha="2026-09-10"):
    return client.post("/api/v1/production/planes", headers=headers, json={
        "almacen_id": ids["almacen_id"], "fecha": fecha, "turno": turno,
        "linea_produccion": linea,
    })


def _agregar_orden(client, headers, plan_id, ids, cantidad="10", key="op-plan-1"):
    return client.post(f"/api/v1/production/planes/{plan_id}/ordenes", headers=headers, json={
        "articulo_id": ids["masa_id"], "cantidad_planeada": cantidad, "idempotency_key": key,
    })


def test_crear_plan_y_listar(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_plan(client, h, ids)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "planificado"
    assert body["origen"] == "cronograma_fijo"

    listado = client.get("/api/v1/production/planes", headers=h).json()
    assert listado["total"] == 1


def test_crear_plan_duplicado_409(env):
    """RN-PRD-012: una línea, un tipo de receta por turno."""
    client, ids, _ = env
    h = _token(client)
    assert _crear_plan(client, h, ids).status_code == 201
    r = _crear_plan(client, h, ids)
    assert r.status_code == 409


def test_agregar_orden_liga_plan_produccion_id(env):
    client, ids, TestSession = env
    h = _token(client)
    plan_id = _crear_plan(client, h, ids).json()["id"]
    r = _agregar_orden(client, h, plan_id, ids)
    assert r.status_code == 201, r.text
    assert r.json()["plan_produccion_id"] == plan_id
    assert r.json()["origen"] == "plan"


def test_agregar_orden_a_plan_ya_iniciado_409(env):
    client, ids, _ = env
    h = _token(client)
    plan_id = _crear_plan(client, h, ids).json()["id"]
    _agregar_orden(client, h, plan_id, ids)
    assert client.post(f"/api/v1/production/planes/{plan_id}/iniciar", headers=h).status_code == 200
    r = _agregar_orden(client, h, plan_id, ids, key="op-plan-2")
    assert r.status_code == 409


def test_iniciar_plan_sin_ordenes_409(env):
    client, ids, _ = env
    h = _token(client)
    plan_id = _crear_plan(client, h, ids).json()["id"]
    r = client.post(f"/api/v1/production/planes/{plan_id}/iniciar", headers=h)
    assert r.status_code == 409


def test_iniciar_plan_reserva_insumos_por_orden(env):
    client, ids, TestSession = env
    h = _token(client)
    plan_id = _crear_plan(client, h, ids).json()["id"]
    orden_id = _agregar_orden(client, h, plan_id, ids, cantidad="10").json()["id"]

    r = client.post(f"/api/v1/production/planes/{plan_id}/iniciar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_ejecucion"

    with TestSession() as s:
        reserva = s.scalar(
            select(ReservaStock).where(
                ReservaStock.referencia_id == uuid.UUID(orden_id),
                ReservaStock.sku_id == uuid.UUID(ids["sku_harina_id"]),
            )
        )
        assert reserva is not None
        assert reserva.tipo == "produccion"
        assert reserva.estado == "activa"
        # factor = 10 planeados / 10 rendimiento = 1; 1 kg de harina por
        # línea de receta * factor 1 = 1 kg.
        assert reserva.cantidad == Decimal("1.0000")


def test_iniciar_plan_sin_stock_suficiente_409(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        stock = s.scalar(
            select(Stock).where(Stock.sku_id == uuid.UUID(ids["sku_harina_id"]))
        )
        stock.cantidad = Decimal("1")  # no alcanza para 100/10 = 10 kg de harina
        s.commit()

    plan_id = _crear_plan(client, h, ids).json()["id"]
    _agregar_orden(client, h, plan_id, ids, cantidad="100")
    r = client.post(f"/api/v1/production/planes/{plan_id}/iniciar", headers=h)
    assert r.status_code == 409

    with TestSession() as s:
        plan = s.get(PlanProduccion, uuid.UUID(plan_id))
        assert plan.estado == "planificado"  # nada se comprometió a medias
        assert s.scalar(
            select(ReservaStock).where(ReservaStock.referencia_id.is_not(None))
        ) is None


def test_registrar_consumo_de_orden_planificada_consume_la_reserva(env):
    client, ids, TestSession = env
    h = _token(client)
    plan_id = _crear_plan(client, h, ids).json()["id"]
    orden_id = _agregar_orden(client, h, plan_id, ids, cantidad="10").json()["id"]
    client.post(f"/api/v1/production/planes/{plan_id}/iniciar", headers=h)

    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["harina_id"], "cantidad": "10", "costo_unitario": "2"}],
        },
    )
    assert r.status_code == 200, r.text

    with TestSession() as s:
        reserva = s.scalar(
            select(ReservaStock).where(ReservaStock.referencia_id == uuid.UUID(orden_id))
        )
        assert reserva.estado == "consumida"


def test_cerrar_plan_libera_lo_no_consumido(env):
    client, ids, TestSession = env
    h = _token(client)
    plan_id = _crear_plan(client, h, ids).json()["id"]
    orden_id = _agregar_orden(client, h, plan_id, ids, cantidad="10").json()["id"]
    client.post(f"/api/v1/production/planes/{plan_id}/iniciar", headers=h)

    r = client.post(f"/api/v1/production/planes/{plan_id}/cerrar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cerrado"

    with TestSession() as s:
        reserva = s.scalar(
            select(ReservaStock).where(ReservaStock.referencia_id == uuid.UUID(orden_id))
        )
        assert reserva.estado == "liberada"


def test_cerrar_plan_planificado_409(env):
    client, ids, _ = env
    h = _token(client)
    plan_id = _crear_plan(client, h, ids).json()["id"]
    r = client.post(f"/api/v1/production/planes/{plan_id}/cerrar", headers=h)
    assert r.status_code == 409


def test_planificar_sin_permiso_403(env):
    client, ids, TestSession = env
    with TestSession() as s:
        cajero = Usuario(username="cajero_plan", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cajero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol.id))
        s.commit()

    h_cajero = _token(client, "cajero_plan", "222222")
    assert _crear_plan(client, h_cajero, ids).status_code == 403
