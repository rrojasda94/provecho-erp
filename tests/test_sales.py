"""Tests del slice Sales/PDV: venta → consumo de stock, cobro → pagada,
idempotencia, anulación → reposición, RBAC."""

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
    Stock,
    UnidadMedida,
)
from src.modules.sales.infrastructure.models import MedioPago, ProductoComercial, PuntoVenta
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Sucursal,
)


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
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        s.add(sucursal)
        s.flush()
        almacen = Almacen(
            empresa_id=empresa.id, sucursal_id=sucursal.id,
            nombre="Almacén Tarapoto", tipo="sucursal",
        )
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador",
            serie_boleta="B001", serie_factura="F001", politica_pago="adelantado",
        )
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([almacen, pv, udm_cat])
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
        s.add(udm)
        s.flush()
        harina = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        s.add(harina)
        s.flush()
        sku = Sku(articulo_id=harina.id, codigo="SKU-HARINA")
        receta = Receta(
            nombre="Pizza base", rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=udm.id,
        )
        s.add_all([sku, receta])
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id,
                         cantidad=Decimal("0.25")))
        producto = ProductoComercial(
            id_interno="P001", marca_id=marca.id, nombre="Pizza Clásica",
            receta_id=receta.id,
        )
        medio = MedioPago(
            empresa_id=empresa.id, nombre="Efectivo", direccion="cobro",
            tipo="efectivo",
        )
        s.add_all([producto, medio])
        s.flush()
        # Stock inicial: 10 kg de harina.
        s.add(Stock(almacen_id=almacen.id, sku_id=sku.id, cantidad=Decimal(10)))
        ids.update(
            sucursal_id=str(sucursal.id), pv_id=str(pv.id),
            producto_id=str(producto.id), medio_id=str(medio.id),
            almacen_id=str(almacen.id), sku_id=str(sku.id),
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


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _venta_body(ids, key="test-venta-0001", cantidad="2"):
    return {
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "takeout", "idempotency_key": key,
        "items": [{
            "producto_comercial_id": ids["producto_id"],
            "cantidad": cantidad, "precio_unitario": "25.00",
        }],
    }


def _stock(ids, TestSession):
    with TestSession() as s:
        return s.scalar(select(Stock)).cantidad


def test_venta_descuenta_stock_por_receta(env):
    client, ids, TestSession = env
    h = _token(client)
    r = client.post("/api/v1/sales/ventas", headers=h, json=_venta_body(ids))
    assert r.status_code == 201
    body = r.json()
    assert body["estado"] == "orden"
    assert Decimal(body["total"]) == Decimal("50.00")
    assert body["numero_orden"] == 1
    # 2 pizzas × 0.25 kg = 0.5 kg consumidos → 9.5.
    assert _stock(ids, TestSession) == Decimal("9.5")


def test_venta_idempotente(env):
    client, ids, TestSession = env
    h = _token(client)
    r1 = client.post("/api/v1/sales/ventas", headers=h, json=_venta_body(ids))
    r2 = client.post("/api/v1/sales/ventas", headers=h, json=_venta_body(ids))
    assert r1.json()["id"] == r2.json()["id"]
    # El stock se descontó UNA sola vez.
    assert _stock(ids, TestSession) == Decimal("9.5")


def test_cobro_parcial_y_total(env):
    client, ids, _ = env
    h = _token(client)
    venta = client.post("/api/v1/sales/ventas", headers=h, json=_venta_body(ids)).json()
    vid = venta["id"]
    p1 = client.post(f"/api/v1/sales/ventas/{vid}/pagos", headers=h, json={
        "medio_pago_id": ids["medio_id"], "monto": "30.00",
        "idempotency_key": "pago-0001",
    })
    assert p1.status_code == 201
    assert client.get(f"/api/v1/sales/ventas/{vid}", headers=h).json()["estado"] == "orden"
    client.post(f"/api/v1/sales/ventas/{vid}/pagos", headers=h, json={
        "medio_pago_id": ids["medio_id"], "monto": "20.00",
        "idempotency_key": "pago-0002",
    })
    assert client.get(f"/api/v1/sales/ventas/{vid}", headers=h).json()["estado"] == "pagada"


def test_sobrepago_409(env):
    client, ids, _ = env
    h = _token(client)
    venta = client.post("/api/v1/sales/ventas", headers=h, json=_venta_body(ids)).json()
    r = client.post(f"/api/v1/sales/ventas/{venta['id']}/pagos", headers=h, json={
        "medio_pago_id": ids["medio_id"], "monto": "60.00",
        "idempotency_key": "pago-sobre",
    })
    assert r.status_code == 409


def test_anular_repone_stock(env):
    client, ids, TestSession = env
    h = _token(client)
    venta = client.post("/api/v1/sales/ventas", headers=h, json=_venta_body(ids)).json()
    assert _stock(ids, TestSession) == Decimal("9.5")
    r = client.post(f"/api/v1/sales/ventas/{venta['id']}/anular", headers=h)
    assert r.status_code == 200
    assert r.json()["estado"] == "anulada"
    assert _stock(ids, TestSession) == Decimal("10")


def test_anular_pagada_409(env):
    client, ids, _ = env
    h = _token(client)
    venta = client.post("/api/v1/sales/ventas", headers=h, json=_venta_body(ids)).json()
    client.post(f"/api/v1/sales/ventas/{venta['id']}/pagos", headers=h, json={
        "medio_pago_id": ids["medio_id"], "monto": "50.00",
        "idempotency_key": "pago-full",
    })
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/anular", headers=h
    ).status_code == 409


def test_correlativo_por_dia_y_sucursal(env):
    client, ids, _ = env
    h = _token(client)
    n1 = client.post("/api/v1/sales/ventas", headers=h,
                     json=_venta_body(ids, key="k-0000001")).json()["numero_orden"]
    n2 = client.post("/api/v1/sales/ventas", headers=h,
                     json=_venta_body(ids, key="k-0000002")).json()["numero_orden"]
    assert (n1, n2) == (1, 2)
