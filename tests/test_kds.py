"""Tests de Cumplimiento de pedido (PROC-OPE-002).

Etapa 1 — preparación en el KDS: pantallas por categoría, bump, avance
real compartido entre pantallas, comanda y RBAC.
Etapa 2 — entrega: cierre del pedido, idempotencia y permiso propio.
"""

import ast
import inspect
import textwrap
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
from src.modules.sales.api import kds_schemas
from src.modules.sales.application import kds as kds_app
from src.modules.sales.infrastructure.models import (
    Atributo,
    AtributoValor,
    ListaPrecio,
    MedioPago,
    Precio,
    ProductoAtributoLinea,
    ProductoAtributoValor,
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
        receta_p = Receta(empresa_id=empresa.id, nombre="Pizza",
                          rendimiento_cantidad=Decimal(1),
                          rendimiento_unidad_medida_id=udm.id)
        receta_b = Receta(empresa_id=empresa.id, nombre="Gaseosa",
                          rendimiento_cantidad=Decimal(1),
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
        supervisor = Usuario(username="super1", pin_hash=hash_pin("555666"),
                             tipo="humano")
        s.add_all([pizza, bebida, medio, cocinero, despachador, supervisor])
        s.flush()
        for usuario, nombre_rol in ((cocinero, "cocinero"),
                                    (despachador, "despachador"),
                                    (supervisor, "supervisor")):
            rol = s.scalar(select(Rol).where(Rol.nombre == nombre_rol))
            s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
            # Sin sucursal asignada el JWT no lleva empresa y el contexto de
            # tenant (ADR-004) le niega todo.
            s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
        # Una MitadXMitad aparte y no atributos sobre la Pizza Clásica:
        # RN-COM-040 exige elegir un valor de cada atributo ofrecido, así que
        # colgárselos a la pizza de siempre volvería invendible al resto de
        # los tests.
        receta_m = Receta(empresa_id=empresa.id, nombre="MitadXMitad",
                          rendimiento_cantidad=Decimal(1),
                          rendimiento_unidad_medida_id=udm.id)
        s.add(receta_m)
        s.flush()
        mxm = ProductoComercial(id_interno="P002", marca_id=marca.id,
                                nombre="Pizza MitadXMitad", receta_id=receta_m.id,
                                categoria_id=cat_pizzas.id)
        s.add(mxm)
        s.flush()
        variantes = {}
        for mitad in ("Mitad 1", "Mitad 2"):
            atributo = Atributo(empresa_id=empresa.id, nombre=mitad,
                                modo_variante="nunca", display="radio")
            s.add(atributo)
            s.flush()
            linea_attr = ProductoAtributoLinea(producto_comercial_id=mxm.id,
                                               atributo_id=atributo.id)
            s.add(linea_attr)
            s.flush()
            for sabor in ("Americana", "Hawaiana"):
                valor = AtributoValor(atributo_id=atributo.id, nombre=sabor)
                s.add(valor)
                s.flush()
                ptav = ProductoAtributoValor(linea_id=linea_attr.id,
                                             atributo_valor_id=valor.id)
                s.add(ptav)
                s.flush()
                variantes[f"{mitad}: {sabor}"] = str(ptav.id)
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
            Precio(lista_precio_id=lista.id, producto_comercial_id=mxm.id,
                   monto=Decimal("32.00")),
        ])
        ids.update(
            sucursal_id=str(sucursal.id), pv_id=str(pv.id),
            cat_pizzas=str(cat_pizzas.id), cat_bebidas=str(cat_bebidas.id),
            pizza_id=str(pizza.id), bebida_id=str(bebida.id),
            mxm_id=str(mxm.id), variantes=variantes,
            marca_id=str(marca.id), receta_pizza=str(receta_p.id),
            lista_precio=str(lista.id),
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


def test_item_tachado_sigue_visible_hasta_terminar_la_estacion(env):
    """Tachar un ítem no lo saca de la pantalla: sigue en la tarjeta con
    estado `listo` (la línea tachada de la cocina) para quien lo tachó y
    para cualquier otra pantalla que muestre ese pedido. El pedido sale de
    la cola recién cuando la estación terminó todo lo suyo."""
    client, ids = env
    h = _token(client)
    _setup_pantallas_y_venta(client, ids, h)
    # Pantalla sin filtro: ve la pizza y la bebida del mismo pedido.
    pase = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Pase", "tipo": "preparacion",
    }).json()

    items = _cola(client, h, pase["id"])[0]["items"]
    assert len(items) == 2

    for estado in ("en_preparacion", "listo"):
        client.post(f"/api/v1/kds/items/{items[0]['venta_item_id']}/avanzar",
                    headers=h, json={"estado": estado})

    cola = _cola(client, h, pase["id"])
    assert len(cola) == 1, "el pedido sigue en cola: falta un ítem"
    estados = {i["venta_item_id"]: i["estado"] for i in cola[0]["items"]}
    assert estados[items[0]["venta_item_id"]] == "listo"  # tachado, visible
    assert estados[items[1]["venta_item_id"]] == "pendiente"

    for estado in ("en_preparacion", "listo"):
        client.post(f"/api/v1/kds/items/{items[1]['venta_item_id']}/avanzar",
                    headers=h, json={"estado": estado})
    assert _cola(client, h, pase["id"]) == []


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


def test_el_supervisor_opera_pero_ya_no_configura(env):
    """Decisión 2026-08-24 (ADR-065): dar de alta o borrar una estación es
    alta de infraestructura del local, no una tarea de turno."""
    client, ids = env
    h_admin = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h_admin)
    h_sup = _token(client, "super1", "555666")

    # Sigue viendo y operando la cocina.
    assert client.get("/api/v1/kds/pantallas", headers=h_sup).status_code == 200
    assert client.get(
        f"/api/v1/kds/pantallas/{horno['id']}/cola", headers=h_sup
    ).status_code == 200

    # Pero no la monta ni la desmonta.
    assert client.post("/api/v1/kds/pantallas", headers=h_sup, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Pirata",
        "tipo": "preparacion",
    }).status_code == 403
    assert client.patch(
        f"/api/v1/kds/pantallas/{horno['id']}", headers=h_sup,
        json={"nombre": "Otro"},
    ).status_code == 403
    assert client.delete(
        f"/api/v1/kds/pantallas/{horno['id']}", headers=h_sup
    ).status_code == 403


def test_borrar_una_pantalla_exige_que_la_cola_este_vacia(env):
    """Borrarla con pedidos encima dejaría esas líneas sin dónde tacharse."""
    client, ids = env
    h = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h)

    assert client.delete(
        f"/api/v1/kds/pantallas/{horno['id']}", headers=h
    ).status_code == 409

    libre = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Postres",
        "tipo": "preparacion", "categoria_ids": [], "orden": 5,
    }).json()
    assert client.delete(
        f"/api/v1/kds/pantallas/{libre['id']}", headers=h
    ).status_code == 204

    nombres = [
        p["nombre"] for p in client.get("/api/v1/kds/pantallas", headers=h).json()
    ]
    assert "Postres" not in nombres
    # El nombre queda libre: la baja es definitiva, no un apagado.
    assert client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Postres",
        "tipo": "preparacion", "orden": 5,
    }).status_code == 201


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


# --- Cadena de estaciones (ADR-044, RN-CUP-013) --------------------------------
def _cadena_de_tres(client, ids, h):
    """Armado(0) → Horno(1) para pizzas; Barra(0) para bebidas; Despacho."""
    def pantalla(nombre, tipo, orden, cats=None):
        return client.post("/api/v1/kds/pantallas", headers=h, json={
            "sucursal_id": ids["sucursal_id"], "nombre": nombre, "tipo": tipo,
            "categoria_ids": cats, "orden": orden,
        }).json()

    armado = pantalla("Armado", "preparacion", 0, [ids["cat_pizzas"]])
    horno = pantalla("Horno", "preparacion", 1, [ids["cat_pizzas"]])
    barra = pantalla("Barra", "preparacion", 0, [ids["cat_bebidas"]])
    despacho = pantalla("Despacho", "despacho", 9)
    client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "mesa", "idempotency_key": "kds-cadena-1",
        "referencia_atencion": "Mesa 9",
        "items": [
            {"producto_comercial_id": ids["pizza_id"], "cantidad": "1"},
            {"producto_comercial_id": ids["bebida_id"], "cantidad": "1"},
        ],
    })
    return armado, horno, barra, despacho


def _tachar(client, h, item_id, desde="pendiente"):
    """Un toque en la pantalla = los pasos que falten hasta `listo`."""
    pasos = ["en_preparacion", "listo"] if desde == "pendiente" else ["listo"]
    for estado in pasos:
        r = client.post(f"/api/v1/kds/items/{item_id}/avanzar", headers=h,
                        json={"estado": estado})
        assert r.status_code == 200, r.text
    return r.json()


def test_la_linea_recorre_la_cadena_de_estaciones(env):
    client, ids = env
    h = _token(client)
    armado, horno, barra, despacho = _cadena_de_tres(client, ids, h)

    # Arranca en el primer eslabón que la atiende, no en el horno.
    pizza = _cola(client, h, armado["id"])[0]["items"][0]
    assert pizza["etapa_kds"] == 0
    assert pizza["estacion"] == "Armado"
    assert _cola(client, h, horno["id"]) == []

    # Tacharla en armado NO la deja lista: la manda al horno.
    salida = _tachar(client, h, pizza["venta_item_id"])
    assert salida["estado"] == "en_preparacion"
    assert salida["etapa_kds"] == 1

    # Armado ya no la tiene pendiente, así que el pedido sale de su cola;
    # el horno la recibe con su nombre a la vista.
    assert _cola(client, h, armado["id"]) == []
    en_horno = _cola(client, h, horno["id"])[0]["items"][0]
    assert en_horno["estacion"] == "Horno"

    # Tacharla en el horno sí, porque no queda cadena por delante.
    final = _tachar(client, h, en_horno["venta_item_id"], desde="en_preparacion")
    assert final["estado"] == "listo"


def test_la_bebida_se_salta_el_horno_sola(env):
    client, ids = env
    h = _token(client)
    armado, horno, barra, _despacho = _cadena_de_tres(client, ids, h)

    bebida = _cola(client, h, barra["id"])[0]["items"][0]
    assert bebida["estacion"] == "Barra"

    # La barra es su único eslabón: el horno no atiende bebidas, así que
    # tacharla la deja lista sin configurar ningún salto.
    assert _tachar(client, h, bebida["venta_item_id"])["estado"] == "listo"

    # La bebida no aparece en el horno ni cuando la pizza sí llega.
    _tachar(client, h, _cola(client, h, armado["id"])[0]["items"][0]["venta_item_id"])
    assert [i["producto"] for i in _cola(client, h, horno["id"])[0]["items"]] == [
        "Pizza Clásica"
    ]


def test_despacho_muestra_en_que_estacion_va_cada_linea(env):
    client, ids = env
    h = _token(client)
    _armado, _horno, barra, despacho = _cadena_de_tres(client, ids, h)

    _tachar(client, h, _cola(client, h, barra["id"])[0]["items"][0]["venta_item_id"])

    pedido = _cola(client, h, despacho["id"])[0]
    porestacion = {i["producto"]: i["estacion"] for i in pedido["items"]}
    # Despacho ve el pedido COMPLETO, con la bebida ya fuera de cocina y la
    # pizza todavía esperando en su estación.
    assert porestacion == {"Pizza Clásica": "Armado", "Gaseosa 500ml": None}
    assert pedido["estado_pedido"] == "pendiente"
    assert pedido["tipo"] == "venta"


def test_despacho_ve_la_direccion_del_delivery(env):
    """La dirección tiene que llegar hasta el navegador: despacho arma la
    bolsa mirando la pantalla, no la comanda impresa."""
    client, ids = env
    h = _token(client)
    horno, _barra, despacho, _venta = _setup_pantallas_y_venta(client, ids, h)
    delivery = client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "delivery", "idempotency_key": "kds-deli-1",
        "direccion_entrega": "Av. Siempre Viva 742",
        "items": [{"producto_comercial_id": ids["pizza_id"], "cantidad": "1"}],
    }).json()

    pizza = next(p for p in _cola(client, h, horno["id"])
                 if p["venta_id"] == delivery["id"])["items"][0]
    _tachar(client, h, pizza["venta_item_id"])

    pedido = next(p for p in _cola(client, h, despacho["id"])
                  if p["venta_id"] == delivery["id"])
    assert pedido["direccion_entrega"] == "Av. Siempre Viva 742"


def test_estacion_desactivada_no_deja_la_linea_invisible(env):
    client, ids = env
    h = _token(client)
    armado, horno, _barra, _despacho = _cadena_de_tres(client, ids, h)

    client.patch(f"/api/v1/kds/pantallas/{armado['id']}", headers=h,
                 json={"activo": False})

    # La pizza estaba en el eslabón 0 y ese eslabón ya no existe: cae al
    # horno en vez de quedarse sin pantalla que la muestre.
    en_horno = _cola(client, h, horno["id"])[0]["items"][0]
    assert en_horno["estacion"] == "Horno"
    assert _tachar(client, h, en_horno["venta_item_id"])["estado"] == "listo"


def test_orden_negativo_se_rechaza(env):
    client, ids = env
    h = _token(client)
    r = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Imposible",
        "tipo": "preparacion", "orden": -1,
    })
    assert r.status_code == 422


def test_despacho_ve_el_pedido_completo_aunque_tenga_categorias(env):
    """Filtrar despacho por categoría lo dejaría viendo media orden, y con
    media orden no se puede contrastar contra la comanda (RN-CUP-004)."""
    client, ids = env
    h = _token(client)
    _armado, _horno, barra, despacho = _cadena_de_tres(client, ids, h)

    # Configurada —mal— para atender solo bebidas.
    client.patch(f"/api/v1/kds/pantallas/{despacho['id']}", headers=h,
                 json={"categoria_ids": [ids["cat_bebidas"]]})
    _tachar(client, h, _cola(client, h, barra["id"])[0]["items"][0]["venta_item_id"])

    pedido = _cola(client, h, despacho["id"])[0]
    assert sorted(i["producto"] for i in pedido["items"]) == [
        "Gaseosa 500ml", "Pizza Clásica",
    ]


# --- El extra no es un plato aparte (RN-CUP-014) --------------------------------
def _pizza_con_sabor(client, ids, h, clave="kds-extra-1", cantidad_extra="1"):
    """Crea el sabor, lo cuelga de la pizza y vende una con él."""
    sabor = client.post("/api/v1/sales/productos", headers=h, json={
        "id_interno": "SPEP", "marca_id": ids["marca_id"], "nombre": "Peperoni",
        "receta_id": ids["receta_pizza"], "es_extra": True,
    }).json()
    r = client.post(f"/api/v1/sales/productos/{ids['pizza_id']}/extras", headers=h,
                    json={"extra_id": sabor["id"], "maximo": 3})
    assert r.status_code == 201, r.text
    # El precio lo resuelve el servidor (RN-PRC-003): sin uno vigente, la
    # venta con el sabor rebota con 409. El sabor no cobra aparte.
    r = client.post(f"/api/v1/sales/listas-precio/{ids['lista_precio']}/precios",
                    headers=h,
                    json={"producto_comercial_id": sabor["id"], "monto": "0.00"})
    assert r.status_code in (200, 201), r.text
    venta = client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "mesa", "idempotency_key": clave,
        "referencia_atencion": "Mesa 1",
        "items": [{
            "producto_comercial_id": ids["pizza_id"], "cantidad": "1",
            "extras": [{"producto_comercial_id": sabor["id"],
                        "cantidad": cantidad_extra}],
        }],
    })
    assert venta.status_code == 201, venta.text
    return sabor, venta.json()


def test_el_sabor_viaja_dentro_del_plato_y_no_como_item_suelto(env):
    client, ids = env
    h = _token(client)
    pantalla = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Cocina", "tipo": "preparacion",
    }).json()
    _pizza_con_sabor(client, ids, h)

    items = _cola(client, h, pantalla["id"])[0]["items"]
    # Antes salían dos tarjetas —"1 Pizza Clásica" y "1 Peperoni"— y el
    # cocinero leía dos platos donde hay uno.
    assert [i["producto"] for i in items] == ["Pizza Clásica"]
    assert items[0]["extras"] == [{"producto": "Peperoni", "cantidad": "1.00"}]


def test_tachar_el_plato_se_lleva_su_extra(env):
    client, ids = env
    h = _token(client)
    pantalla = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Cocina", "tipo": "preparacion",
    }).json()
    _, venta = _pizza_con_sabor(client, ids, h)

    linea = _cola(client, h, pantalla["id"])[0]["items"][0]["venta_item_id"]
    _tachar(client, h, linea)

    # `estado_pedido` y `pedido_entregable` suman TODOS los ítems: si el
    # extra se quedara atrás, el pedido no se podría entregar nunca.
    avance = client.get(f"/api/v1/kds/ventas/{venta['id']}/avance", headers=h).json()
    assert avance["estado_pedido"] == "listo"
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h
    ).status_code == 200


def test_con_estaciones_filtradas_el_extra_sin_categoria_no_cuelga_el_pedido(env):
    """El ruteo mira la categoría del PLATO, no la del extra.

    El sabor se crea sin `categoria_id`, así que una estación filtrada no lo
    atendería: como ítem suelto se quedaba `pendiente` para siempre y el
    pedido nunca llegaba a entregable.
    """
    client, ids = env
    h = _token(client)
    horno = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Horno", "tipo": "preparacion",
        "categoria_ids": [ids["cat_pizzas"]],
    }).json()
    _, venta = _pizza_con_sabor(client, ids, h)

    _tachar(client, h, _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"])
    assert client.get(
        f"/api/v1/kds/ventas/{venta['id']}/avance", headers=h
    ).json()["estado_pedido"] == "listo"


def test_la_comanda_sangra_el_extra_bajo_su_plato(env):
    client, ids = env
    h = _token(client)
    _, venta = _pizza_con_sabor(client, ids, h, cantidad_extra="2")

    texto = client.post(
        f"/api/v1/kds/ventas/{venta['id']}/comanda", headers=h
    ).json()["texto"]
    lineas = [línea for línea in texto.splitlines() if "PIZZA" in línea.upper()
              or "PEPERONI" in línea.upper()]
    # En el papel, "1x Pizza" seguido de "2x Peperoni" al mismo nivel se lee
    # como dos platos distintos.
    assert lineas == ["1x Pizza Clásica", "   + 2x PEPERONI"]


def _venta_mitad_y_mitad(client, ids, h, clave="kds-mxm-1"):
    return client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "mesa", "idempotency_key": clave,
        "referencia_atencion": "Mesa 9",
        "items": [{
            "producto_comercial_id": ids["mxm_id"], "cantidad": "1",
            "valores_variante_ids": [
                ids["variantes"]["Mitad 1: Americana"],
                ids["variantes"]["Mitad 2: Hawaiana"],
            ],
        }],
    }).json()


def test_la_estacion_ve_de_que_mitades_es_la_pizza(env):
    """Un pizzero que trabaja solo con la pantalla tiene que ver las mitades:
    en una MitadXMitad son lo único que dice qué se prepara (ADR-056)."""
    client, ids = env
    h = _token(client)
    horno, _barra, _despacho, _venta = _setup_pantallas_y_venta(client, ids, h)
    mxm = _venta_mitad_y_mitad(client, ids, h)

    pedido = next(p for p in _cola(client, h, horno["id"])
                  if p["venta_id"] == mxm["id"])
    assert pedido["items"][0]["valores"] == [
        "Mitad 1: Americana", "Mitad 2: Hawaiana"
    ]


def test_despacho_tambien_ve_las_mitades(env):
    """La misma línea vista desde la otra pantalla: si solo una de las dos
    ramas de `_items_de_pantalla` pasa los valores, el plato se contrasta
    contra la comanda con menos información de la que trae el papel."""
    client, ids = env
    h = _token(client)
    horno, _barra, despacho, _venta = _setup_pantallas_y_venta(client, ids, h)
    mxm = _venta_mitad_y_mitad(client, ids, h)

    linea = next(p for p in _cola(client, h, horno["id"])
                 if p["venta_id"] == mxm["id"])["items"][0]
    _tachar(client, h, linea["venta_item_id"])

    pedido = next(p for p in _cola(client, h, despacho["id"])
                  if p["venta_id"] == mxm["id"])
    assert pedido["items"][0]["valores"] == [
        "Mitad 1: Americana", "Mitad 2: Hawaiana"
    ]


def test_la_pizza_de_siempre_no_inventa_mitades(env):
    """Un producto sin atributos no trae `valores`: la lista vacía es lo que
    hace que la tarjeta no muestre un bloque en blanco."""
    client, ids = env
    h = _token(client)
    horno, _barra, _despacho, _venta = _setup_pantallas_y_venta(client, ids, h)
    assert _cola(client, h, horno["id"])[0]["items"][0]["valores"] == []


def _claves_emitidas(funcion) -> set[str]:
    """Las claves literales de los dicts que la función construye."""
    arbol = ast.parse(textwrap.dedent(inspect.getsource(funcion)))
    return {
        clave.value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Dict)
        for clave in nodo.keys
        if isinstance(clave, ast.Constant) and isinstance(clave.value, str)
    }


def test_el_response_model_no_se_come_ningun_campo_de_la_cola():
    """El agujero de ADR-044, cerrado de raíz: un campo que el caso de uso
    calcula y mete en el dict pero el schema no declara lo filtra FastAPI en
    silencio —sin error, sin warning, sin campo en la pantalla—. Pasó con
    `tipo`/`consumo_motivo`, volvió a pasar con `direccion_entrega` y
    `valores`. Este test falla en el commit que lo repita, sin importar qué
    campo sea.
    """
    declarados = {
        kds_app.cola_pantalla: set(kds_schemas.PedidoColaOut.model_fields)
        | set(kds_schemas.ItemColaOut.model_fields),
        kds_app._item_a_dict: set(kds_schemas.ItemColaOut.model_fields)
        | set(kds_schemas.ExtraColaOut.model_fields),
        kds_app.avance_venta: set(kds_schemas.AvanceOut.model_fields)
        | set(kds_schemas.ItemColaOut.model_fields),
        kds_app.comanda: set(kds_schemas.ComandaOut.model_fields),
    }
    for funcion, campos in declarados.items():
        sobrantes = _claves_emitidas(funcion) - campos
        assert not sobrantes, (
            f"{funcion.__name__} emite {sorted(sobrantes)} y el schema no lo "
            f"declara: el response_model los va a filtrar en silencio"
        )
