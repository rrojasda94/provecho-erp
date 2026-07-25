"""Tests del KDS: pantallas por categoría, bump, avance real compartido
entre pantallas, comanda y RBAC."""

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
from src.modules.sales.infrastructure.models import (
    MedioPago,
    ProductoComercial,
    PuntoVenta,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
)
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
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        s.add(sucursal)
        s.flush()
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador",
            serie_boleta="B001", serie_factura="F001", politica_pago="adelantado",
        )
        cat_pizzas = Categoria(empresa_id=empresa.id, nombre="Pizzas")
        cat_bebidas = Categoria(empresa_id=empresa.id, nombre="Bebidas")
        udm_cat = CategoriaUdm(nombre="Unidad")
        s.add_all([pv, cat_pizzas, cat_bebidas, udm_cat])
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Unidad")
        s.add(udm)
        s.flush()
        # Recetas sin insumos: KDS no necesita stock para este test.
        receta_p = Receta(nombre="Pizza", rendimiento_cantidad=Decimal(1),
                          rendimiento_unidad_medida_id=udm.id)
        receta_b = Receta(nombre="Gaseosa", rendimiento_cantidad=Decimal(1),
                          rendimiento_unidad_medida_id=udm.id)
        s.add_all([receta_p, receta_b])
        s.flush()
        pizza = ProductoComercial(id_interno="P001", marca_id=marca.id,
                                  nombre="Pizza Clásica", receta_id=receta_p.id,
                                  categoria_id=cat_pizzas.id)
        bebida = ProductoComercial(id_interno="B001", marca_id=marca.id,
                                   nombre="Gaseosa 500ml", receta_id=receta_b.id,
                                   categoria_id=cat_bebidas.id)
        medio = MedioPago(empresa_id=empresa.id, nombre="Efectivo",
                          direccion="cobro", tipo="efectivo")
        cocinero = Usuario(username="cocinero1", pin_hash=hash_pin("111222"),
                           tipo="humano")
        s.add_all([pizza, bebida, medio, cocinero])
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
        s.add(UsuarioRol(usuario_id=cocinero.id, rol_id=rol.id))
        ids.update(
            sucursal_id=str(sucursal.id), pv_id=str(pv.id),
            cat_pizzas=str(cat_pizzas.id), cat_bebidas=str(cat_bebidas.id),
            pizza_id=str(pizza.id), bebida_id=str(bebida.id),
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
        yield c, ids


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_pantallas_y_venta(client, ids, h):
    horno = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Horno",
        "tipo": "preparacion", "categoria_ids": [ids["cat_pizzas"]],
    }).json()
    barra = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Barra",
        "tipo": "preparacion", "categoria_ids": [ids["cat_bebidas"]],
    }).json()
    despacho = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Despacho",
        "tipo": "despacho",
    }).json()
    venta = client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "mesa", "idempotency_key": "kds-venta-1",
        "referencia_atencion": "Mesa 5",
        "items": [
            {"producto_comercial_id": ids["pizza_id"], "cantidad": "1",
             "precio_unitario": "25.00"},
            {"producto_comercial_id": ids["bebida_id"], "cantidad": "2",
             "precio_unitario": "5.00"},
        ],
    }).json()
    return horno, barra, despacho, venta


def _cola(client, h, pantalla_id):
    return client.get(f"/api/v1/kds/pantallas/{pantalla_id}/cola", headers=h).json()


def test_pantallas_filtran_por_categoria(env):
    client, ids = env
    h = _token(client)
    horno, barra, despacho, venta = _setup_pantallas_y_venta(client, ids, h)

    cola_horno = _cola(client, h, horno["id"])
    assert len(cola_horno) == 1
    assert cola_horno[0]["referencia_atencion"] == "Mesa 5"
    assert [i["producto"] for i in cola_horno[0]["items"]] == ["Pizza Clásica"]

    cola_barra = _cola(client, h, barra["id"])
    assert [i["producto"] for i in cola_barra[0]["items"]] == ["Gaseosa 500ml"]

    # Despacho: nada listo aún → vacío.
    assert _cola(client, h, despacho["id"]) == []


def test_avance_real_compartido_entre_pantallas(env):
    client, ids = env
    h = _token(client)
    horno, barra, despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    item_pizza = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    item_bebida = _cola(client, h, barra["id"])[0]["items"][0]["venta_item_id"]

    # Horno avanza la pizza hasta listo.
    for estado in ("en_preparacion", "listo"):
        r = client.post(f"/api/v1/kds/items/{item_pizza}/avanzar", headers=h,
                        json={"estado": estado})
        assert r.status_code == 200

    # Horno ya no la muestra; despacho SÍ ve el pedido con avance real:
    # pizza lista pero pedido aún atrasado por la bebida.
    assert _cola(client, h, horno["id"]) == []
    cola_desp = _cola(client, h, despacho["id"])
    assert len(cola_desp) == 1
    assert cola_desp[0]["estado_pedido"] == "pendiente"  # bebida sin empezar

    # Barra termina la bebida → pedido completo listo.
    for estado in ("en_preparacion", "listo"):
        client.post(f"/api/v1/kds/items/{item_bebida}/avanzar", headers=h,
                    json={"estado": estado})
    avance = client.get(f"/api/v1/kds/ventas/{venta['id']}/avance", headers=h).json()
    assert avance["estado_pedido"] == "listo"

    # Entrega ambos → pedido sale de todas las colas.
    client.post(f"/api/v1/kds/items/{item_pizza}/avanzar", headers=h,
                json={"estado": "entregado"})
    client.post(f"/api/v1/kds/items/{item_bebida}/avanzar", headers=h,
                json={"estado": "entregado"})
    assert _cola(client, h, despacho["id"]) == []


def test_no_retroceso(env):
    client, ids = env
    h = _token(client)
    horno, _, _, venta = _setup_pantallas_y_venta(client, ids, h)
    item = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                json={"estado": "en_preparacion"})
    # Saltarse un estado o retroceder → 409.
    assert client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                       json={"estado": "entregado"}).status_code == 409
    assert client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                       json={"estado": "pendiente"}).status_code == 409


def test_comanda_y_reimpresion(env):
    client, ids = env
    h = _token(client)
    _, _, _, venta = _setup_pantallas_y_venta(client, ids, h)
    c1 = client.post(f"/api/v1/kds/ventas/{venta['id']}/comanda", headers=h).json()
    assert not c1["reimpresion"]
    assert f"ORDEN #{venta['numero_orden']}" in c1["texto"]
    assert "MESA 5" in c1["texto"]
    assert "1x Pizza Cl" in c1["texto"]
    assert "2x Gaseosa" in c1["texto"]
    c2 = client.post(f"/api/v1/kds/ventas/{venta['id']}/comanda", headers=h).json()
    assert c2["reimpresion"] and c2["impresa_veces"] == 2
    assert "REIMPRESION" in c2["texto"]


def test_rbac_cocinero_opera_pero_no_configura(env):
    client, ids = env
    h_admin = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h_admin)
    h_coc = _token(client, "cocinero1", "111222")
    # Puede ver cola.
    assert client.get(
        f"/api/v1/kds/pantallas/{horno['id']}/cola", headers=h_coc
    ).status_code == 200
    # No puede crear pantallas.
    assert client.post("/api/v1/kds/pantallas", headers=h_coc, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Pirata",
        "tipo": "preparacion",
    }).status_code == 403


def test_pantalla_sin_categorias_ve_todo(env):
    client, ids = env
    h = _token(client)
    todo = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "General",
        "tipo": "preparacion",
    }).json()
    client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "mesa", "idempotency_key": "kds-venta-2",
        "items": [
            {"producto_comercial_id": ids["pizza_id"], "cantidad": "1",
             "precio_unitario": "25.00"},
            {"producto_comercial_id": ids["bebida_id"], "cantidad": "1",
             "precio_unitario": "5.00"},
        ],
    })
    cola = _cola(client, h, todo["id"])
    assert len(cola[0]["items"]) == 2
