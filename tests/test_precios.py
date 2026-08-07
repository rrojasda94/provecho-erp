"""Tests de precio server-side (RN-PRC-003): el PDV no manda el monto.

Cubre resolución por ámbito (sucursal/canal/modalidad), promoción que gana
mientras está vigente y se restaura sola al vencer, y venta sin precio.
"""

import uuid
from datetime import date, timedelta
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
    Categoria,
    CategoriaUdm,
    Receta,
    UnidadMedida,
)
from src.modules.sales.infrastructure.models import ProductoComercial, PuntoVenta
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Sucursal,
)
from src.shared import fechas

HOY = fechas.hoy()
AYER = HOY - timedelta(days=1)
MANANA = HOY + timedelta(days=1)


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
            marca_id=marca.id, empresa_id=empresa.id, nombre="Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([sucursal, udm_cat])
        s.flush()
        pv = PuntoVenta(sucursal_id=sucursal.id, canal="trabajador",
                        serie_boleta="B001", serie_factura="F001",
                        politica_pago="adelantado")
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
        s.add_all([pv, udm])
        s.flush()
        receta = Receta(empresa_id=empresa.id, nombre="Pizza",
                        rendimiento_cantidad=Decimal(1),
                        rendimiento_unidad_medida_id=udm.id)
        s.add(receta)
        s.flush()
        producto = ProductoComercial(id_interno="P001", marca_id=marca.id,
                                     nombre="Pizza Clásica", receta_id=receta.id)
        s.add(producto)
        s.flush()
        ids.update(sucursal_id=str(sucursal.id), pv_id=str(pv.id),
                   marca_id=str(marca.id), producto_id=str(producto.id))
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
        yield c, ids


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _lista(client, h, ids, monto, **campos):
    body = {
        "marca_id": ids["marca_id"], "nombre": campos.pop("nombre", "Lista"),
        "vigente_desde": str(campos.pop("vigente_desde", AYER)),
        **{k: (str(v) if isinstance(v, date) else v) for k, v in campos.items()},
    }
    r = client.post("/api/v1/sales/listas-precio", headers=h, json=body)
    assert r.status_code == 201, r.text
    lista_id = r.json()["id"]
    rp = client.post(f"/api/v1/sales/listas-precio/{lista_id}/precios", headers=h,
                     json={"producto_comercial_id": ids["producto_id"],
                           "monto": str(monto)})
    assert rp.status_code == 201, rp.text
    return lista_id


def _venta(client, h, ids, key, modalidad="takeout", canal="pdv"):
    return client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": canal, "modalidad": modalidad, "idempotency_key": key,
        "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "2"}],
    })


def test_venta_sin_precio_vigente_409(env):
    client, ids = env
    h = _token(client)
    r = _venta(client, h, ids, "sin-precio-01")
    assert r.status_code == 409
    assert "precio" in r.json()["detail"].lower()


def test_precio_lo_fija_el_servidor(env):
    client, ids = env
    h = _token(client)
    _lista(client, h, ids, "20.00")
    r = _venta(client, h, ids, "precio-serv-01")
    assert r.status_code == 201
    assert Decimal(r.json()["total"]) == Decimal("40.00")  # 2 × 20


def test_lista_mas_especifica_gana(env):
    client, ids = env
    h = _token(client)
    _lista(client, h, ids, "20.00", nombre="General")
    _lista(client, h, ids, "18.00", nombre="Delivery",
           modalidad="delivery")
    # takeout usa la general; delivery usa la específica.
    assert Decimal(_venta(client, h, ids, "esp-0000001").json()["total"]) == Decimal("40.00")
    r = _venta(client, h, ids, "esp-0000002", modalidad="delivery")
    assert Decimal(r.json()["total"]) == Decimal("36.00")


def test_promocion_gana_y_se_restaura_al_vencer(env):
    client, ids = env
    h = _token(client)
    _lista(client, h, ids, "20.00", nombre="Regular")
    _lista(client, h, ids, "15.00", nombre="Promo julio", es_promocional=True,
           vigente_hasta=HOY)
    assert Decimal(_venta(client, h, ids, "promo-000001").json()["total"]) == Decimal("30.00")

    # Vencida ayer: el precio regular vuelve solo, sin tocar nada.
    _lista(client, h, ids, "12.00", nombre="Promo junio", es_promocional=True,
           vigente_desde=AYER - timedelta(days=10), vigente_hasta=AYER)
    assert Decimal(_venta(client, h, ids, "promo-000002").json()["total"]) == Decimal("30.00")


def test_promocion_sin_fin_409(env):
    client, ids = env
    h = _token(client)
    r = client.post("/api/v1/sales/listas-precio", headers=h, json={
        "marca_id": ids["marca_id"], "nombre": "Promo eterna",
        "vigente_desde": str(AYER), "es_promocional": True,
    })
    assert r.status_code == 409


def test_precio_duplicado_en_la_misma_lista_409(env):
    client, ids = env
    h = _token(client)
    lista_id = _lista(client, h, ids, "20.00")
    r = client.post(f"/api/v1/sales/listas-precio/{lista_id}/precios", headers=h,
                    json={"producto_comercial_id": ids["producto_id"],
                          "monto": "99.00"})
    assert r.status_code == 409


def test_carta_expone_precio_resuelto(env):
    client, ids = env
    h = _token(client)
    _lista(client, h, ids, "20.00")
    r = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    )
    assert r.status_code == 200
    carta = r.json()
    assert len(carta) == 1
    assert Decimal(carta[0]["precio_unitario"]) == Decimal("20.00")


def test_carta_expone_nombre_de_categoria(env):
    """El PDV agrupa el catálogo por categoría (pizzas, bebidas...); sin el
    nombre resuelto solo tendría el id para pintar la pestaña."""
    client, ids = env
    h = _token(client)
    _lista(client, h, ids, "20.00")

    session = next(client.app.dependency_overrides[get_db]())
    empresa = session.scalar(select(Empresa))
    categoria = Categoria(empresa_id=empresa.id, nombre="Pizzas")
    session.add(categoria)
    session.flush()
    producto = session.get(ProductoComercial, uuid.UUID(ids["producto_id"]))
    producto.categoria_id = categoria.id
    session.commit()

    r = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    )
    assert r.status_code == 200
    carta = r.json()
    assert carta[0]["categoria_nombre"] == "Pizzas"


def test_carta_omite_producto_sin_precio(env):
    client, ids = env
    h = _token(client)
    r = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    )
    assert r.json() == []


def test_lista_vigente_a_futuro_no_aplica(env):
    client, ids = env
    h = _token(client)
    _lista(client, h, ids, "20.00", nombre="Regular")
    _lista(client, h, ids, "5.00", nombre="Futura", vigente_desde=MANANA)
    assert Decimal(_venta(client, h, ids, "fut-0000001").json()["total"]) == Decimal("40.00")
