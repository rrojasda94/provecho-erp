"""Tests de Cumplimiento de pedido (PROC-OPE-002).

Etapa 1 — preparación en el KDS: pantallas por categoría, bump, avance
real compartido entre pantallas, comanda y RBAC.
Etapa 2 — entrega: cierre del pedido, idempotencia y permiso propio.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.core.events import event_bus
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Categoria,
    CategoriaUdm,
    Receta,
    UnidadMedida,
)
from src.modules.sales.infrastructure.models import (
    ListaPrecio,
    MedioPago,
    Precio,
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
    UsuarioSucursal,
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
        despachador = Usuario(username="despacho1", pin_hash=hash_pin("333444"),
                              tipo="humano")
        s.add_all([pizza, bebida, medio, cocinero, despachador])
        s.flush()
        for usuario, nombre_rol in ((cocinero, "cocinero"),
                                    (despachador, "despachador")):
            rol = s.scalar(select(Rol).where(Rol.nombre == nombre_rol))
            s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
            # Sin sucursal asignada el JWT no lleva empresa y el contexto de
            # tenant (ADR-004) le niega todo.
            s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
        # Precio server-side (RN-PRC-003): sin lista vigente no hay venta.
        lista = ListaPrecio(marca_id=marca.id, nombre="Regular",
                            vigente_desde=date(2020, 1, 1))
        s.add(lista)
        s.flush()
        s.add_all([
            Precio(lista_precio_id=lista.id, producto_comercial_id=pizza.id,
                   monto=Decimal("25.00")),
            Precio(lista_precio_id=lista.id, producto_comercial_id=bebida.id,
                   monto=Decimal("5.00")),
        ])
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
            {"producto_comercial_id": ids["pizza_id"], "cantidad": "1"},
            {"producto_comercial_id": ids["bebida_id"], "cantidad": "2"},
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

    # La entrega cierra el pedido completo → sale de todas las colas.
    client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)
    assert _cola(client, h, despacho["id"]) == []


def test_no_retroceso(env):
    client, ids = env
    h = _token(client)
    horno, _, _, venta = _setup_pantallas_y_venta(client, ids, h)
    item = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    # Saltarse un estado → 409.
    assert client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                       json={"estado": "listo"}).status_code == 409
    client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                json={"estado": "en_preparacion"})
    # Retroceder → 409.
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


def _dejar_pedido_listo(client, h, horno, barra):
    for pantalla in (horno, barra):
        item = _cola(client, h, pantalla["id"])[0]["items"][0]["venta_item_id"]
        for estado in ("en_preparacion", "listo"):
            client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                        json={"estado": estado})


def test_entrega_exige_pedido_listo(env):
    client, ids = env
    h = _token(client)
    horno, _, _, venta = _setup_pantallas_y_venta(client, ids, h)
    # Nada preparado todavía → no se entrega (RN-CUP-005).
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h
    ).status_code == 409

    # Solo la pizza lista: la bebida sigue pendiente → sigue sin entregarse.
    item_pizza = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    for estado in ("en_preparacion", "listo"):
        client.post(f"/api/v1/kds/items/{item_pizza}/avanzar", headers=h,
                    json={"estado": estado})
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h
    ).status_code == 409


def test_entrega_cierra_el_pedido_y_es_idempotente(env):
    client, ids = env
    h = _token(client)
    horno, barra, despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)

    eventos = []
    event_bus.subscribe("sales.venta_entregada", eventos.append)

    r = client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)
    assert r.status_code == 200
    assert r.json()["estado_pedido"] == "entregado"
    assert r.json()["ya_entregado"] is False
    assert len(eventos) == 1
    assert eventos[0]["venta_id"] == venta["id"]
    assert eventos[0]["modalidad"] == "mesa"

    avance = client.get(f"/api/v1/kds/ventas/{venta['id']}/avance", headers=h).json()
    assert [i["estado"] for i in avance["items"]] == ["entregado", "entregado"]
    assert _cola(client, h, despacho["id"]) == []

    # Repetir la entrega no reemite el evento (RN-CUP-005).
    r2 = client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)
    assert r2.status_code == 200 and r2.json()["ya_entregado"] is True
    assert len(eventos) == 1


def test_cocina_no_entrega_pero_despacho_si(env):
    client, ids = env
    h = _token(client)
    horno, barra, _, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)

    # El cocinero opera el KDS pero no cierra la entrega (RN-CUP-006).
    h_coc = _token(client, "cocinero1", "111222")
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h_coc
    ).status_code == 403
    # Tampoco por la puerta de atrás: el bump no llega a `entregado`.
    item = _cola(client, h, horno["id"])
    assert item == []  # ya está listo, fuera de la cola del horno

    h_desp = _token(client, "despacho1", "333444")
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h_desp
    ).status_code == 200


def test_bump_no_marca_entregado(env):
    client, ids = env
    h = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h)
    item = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    for estado in ("en_preparacion", "listo"):
        client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                    json={"estado": estado})
    # `entregado` no se marca ítem por ítem desde cocina (RN-CUP-005/006).
    r = client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                    json={"estado": "entregado"})
    assert r.status_code == 409
    assert "entrega" in r.json()["detail"]


def test_venta_anulada_no_se_entrega(env):
    client, ids = env
    h = _token(client)
    horno, barra, _, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)
    client.post(f"/api/v1/sales/ventas/{venta['id']}/anular", headers=h)
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h
    ).status_code == 409


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
            {"producto_comercial_id": ids["pizza_id"], "cantidad": "1"},
            {"producto_comercial_id": ids["bebida_id"], "cantidad": "1"},
        ],
    })
    cola = _cola(client, h, todo["id"])
    assert len(cola[0]["items"]) == 2
