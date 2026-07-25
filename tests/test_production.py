"""Tests del slice production core: orden de producción (crear → consumo
→ completar). SQLite en memoria + override de get_db, mismo patrón que
test_purchases.py.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    UnidadMedida,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa, Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(listeners, "session_factory", TestSession)

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
            unidad_medida_id=udm.id, tipo="subreceta",
        )
        s.add_all([harina, masa])
        s.flush()
        s.add(Sku(articulo_id=harina.id, codigo="SKU-HARINA"))
        s.add(Sku(articulo_id=masa.id, codigo="SKU-MASA"))
        s.flush()

        receta = Receta(
            nombre="Masa madre (BOM)", rendimiento_cantidad=Decimal(10),
            rendimiento_unidad_medida_id=udm.id, articulo_id=masa.id,
        )
        s.add(receta)
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal(1)))
        s.flush()

        # Stock inicial de harina para poder consumirla.
        from src.modules.inventory.infrastructure.models import Stock
        sku_harina = s.scalar(select(Sku).where(Sku.articulo_id == harina.id))
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


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_orden(client, headers, ids, idempotency_key="op-key-1", cantidad="10"):
    return client.post("/api/v1/production/ordenes", headers=headers, json={
        "articulo_id": ids["masa_id"],
        "almacen_id": ids["almacen_id"],
        "cantidad_planeada": cantidad,
        "idempotency_key": idempotency_key,
    })


def _consumo_body(ids, cantidad="10", costo="2.00"):
    return {
        "items": [
            {"articulo_id": ids["harina_id"], "cantidad": cantidad, "costo_unitario": costo}
        ],
    }


def test_crear_orden_sin_receta_409(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/production/ordenes", headers=h, json={
        "articulo_id": ids["harina_id"],  # harina no tiene receta propia
        "almacen_id": ids["almacen_id"],
        "cantidad_planeada": "5",
        "idempotency_key": "op-sin-receta",
    })
    assert r.status_code == 409


def test_flujo_completo_conforme_actualiza_stock_y_costo(env):
    client, ids, TestSession = env
    h = _token(client)
    orden = _crear_orden(client, h, ids)
    assert orden.status_code == 201
    orden_id = orden.json()["id"]
    assert orden.json()["estado"] == "borrador"

    consumo = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h,
        json=_consumo_body(ids),
    )
    assert consumo.status_code == 200
    assert consumo.json()["estado"] == "en_proceso"

    completar = client.post(
        f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
            "resultado": "conforme", "cantidad_producida": "10", "horas_hombre": "2",
        },
    )
    assert completar.status_code == 200
    body = completar.json()
    assert body["estado"] == "conforme"
    assert Decimal(body["costo_insumos"]) == Decimal("20.00")
    # 2 horas * 15.00 (tarifa semilla) = 30; (20+30)/10 producido = 5.
    assert Decimal(body["costo_real_unitario"]) == Decimal("5.0000000000")

    stock = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['almacen_id']}", headers=h
    ).json()
    por_sku = {s["sku_id"]: Decimal(s["cantidad"]) for s in stock}
    assert Decimal("990") in por_sku.values()  # harina: 1000 - 10
    assert Decimal("10") in por_sku.values()  # masa producida

    with TestSession() as s:
        masa = s.get(Articulo, uuid.UUID(ids["masa_id"]))
        assert masa.costo_promedio == Decimal("5.0000")


def test_completar_no_conforme_reprocesado_sin_merma(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-2").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_reprocesado",
    })
    assert r.status_code == 200
    assert r.json()["estado"] == "no_conforme_reprocesado"
    assert r.json()["merma_cantidad"] is None


def test_completar_desechado_sin_evidencia_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-3").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_desechado", "merma_cantidad": "10",
        "merma_motivo": "contaminación",
    })
    assert r.status_code == 409


def test_completar_desechado_con_evidencia_ok(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-4").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_desechado", "merma_cantidad": "10",
        "merma_motivo": "contaminación", "evidencia_destruccion_url": "https://x/evidencia.jpg",
    })
    assert r.status_code == 200
    assert r.json()["estado"] == "no_conforme_desechado"
    assert r.json()["merma_motivo"] == "contaminación"


def test_registrar_consumo_estado_invalido_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-5").json()["id"]
    body = _consumo_body(ids)
    assert client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=body
    ).status_code == 200
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=body)
    assert r.status_code == 409


def test_completar_sin_consumo_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-6").json()["id"]
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
    })
    assert r.status_code == 409


def test_idempotencia_crear_orden(env):
    client, ids, _ = env
    h = _token(client)
    r1 = _crear_orden(client, h, ids, idempotency_key="op-key-7")
    r2 = _crear_orden(client, h, ids, idempotency_key="op-key-7")
    assert r1.json()["id"] == r2.json()["id"]


def test_rol_sin_permiso_production_403(env):
    client, ids, TestSession = env
    with TestSession() as s:
        cajero = Usuario(username="cajero_test", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cajero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol.id))
        s.commit()

    h_cajero = _token(client, "cajero_test", "222222")
    r = _crear_orden(client, h_cajero, ids, idempotency_key="op-key-8")
    assert r.status_code == 403
