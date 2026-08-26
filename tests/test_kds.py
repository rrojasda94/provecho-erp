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
        # Una segunda sucursal, sin pantallas: es contra ella que se prueba
        # mudar una estación (una tablet que se lleva al local nuevo).
        sucursal_b = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Norte",
            direccion="Jr. Y 456", tenencia="alquilada",
        )
        s.add_all([sucursal, sucursal_b])
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
            sucursal_id=str(sucursal.id), sucursal_b=str(sucursal_b.id),
            pv_id=str(pv.id),
            cat_pizzas=str(cat_pizzas.id), cat_bebidas=str(cat_bebidas.id),
            pizza_id=str(pizza.id), bebida_id=str(bebida.id),
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


def test_avanzar_no_salta_ni_retrocede(env):
    """`/avanzar` sigue siendo estrictamente hacia adelante y de a un paso.
    Deshacer tiene su propia puerta (`/retroceder`): si `/avanzar` aceptara
    ir para atrás, un `estado` mal calculado en el cliente desharía trabajo
    creyendo que lo adelanta."""
    client, ids = env
    h = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h)
    item = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    # Saltarse un estado → 409.
    assert client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                       json={"estado": "listo"}).status_code == 409
    client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                json={"estado": "en_preparacion"})
    # Retroceder por la puerta de avanzar → 409.
    assert client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                       json={"estado": "pendiente"}).status_code == 409


def test_deshacer_un_paso_devuelve_el_estado(env):
    """El toque equivocado con las manos ocupadas: se marca en preparación un
    plato que todavía no se empezó."""
    client, ids = env
    h = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h)
    item = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    client.post(f"/api/v1/kds/items/{item}/avanzar", headers=h,
                json={"estado": "en_preparacion"})

    r = client.post(f"/api/v1/kds/items/{item}/retroceder", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "pendiente"


def test_sin_avance_no_hay_nada_que_deshacer(env):
    client, ids = env
    h = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h)
    item = _cola(client, h, horno["id"])[0]["items"][0]["venta_item_id"]
    r = client.post(f"/api/v1/kds/items/{item}/retroceder", headers=h)
    assert r.status_code == 409, r.text


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


def test_una_pantalla_se_muda_de_sucursal(env):
    """Una tablet que se lleva al local nuevo no tiene por qué obligar a
    recrear la estación —y perder su historia— en la otra sucursal."""
    client, ids = env
    h = _token(client)
    pantalla = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Postres",
        "tipo": "preparacion", "categoria_ids": [], "orden": 5,
    }).json()

    r = client.patch(
        f"/api/v1/kds/pantallas/{pantalla['id']}",
        headers=h,
        json={"sucursal_id": ids["sucursal_b"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sucursal_id"] == ids["sucursal_b"]

    # Y deja de verse desde la sucursal de origen.
    origen = client.get(
        f"/api/v1/kds/pantallas?sucursal_id={ids['sucursal_id']}", headers=h
    ).json()
    assert pantalla["id"] not in [p["id"] for p in origen]


def test_mudar_una_pantalla_con_cola_deja_pedidos_invisibles(env):
    """Mismo criterio que borrarla: las líneas que están pasando por esta
    estación quedarían esperando en una cocina que ya no las mira."""
    client, ids = env
    h = _token(client)
    horno, _, _, _ = _setup_pantallas_y_venta(client, ids, h)

    r = client.patch(
        f"/api/v1/kds/pantallas/{horno['id']}",
        headers=h,
        json={"sucursal_id": ids["sucursal_b"]},
    )
    assert r.status_code == 409, r.text
    assert "cola" in r.json()["detail"]


def test_mudarla_a_una_sucursal_que_ya_tiene_ese_nombre_es_409(env):
    """El índice único es `(sucursal_id, nombre)` entre las vivas: sin este
    chequeo lo que sale es un IntegrityError que no le dice nada a nadie."""
    client, ids = env
    h = _token(client)
    aca = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "nombre": "Horno", "tipo": "preparacion",
    }).json()
    client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_b"], "nombre": "Horno", "tipo": "preparacion",
    })

    r = client.patch(
        f"/api/v1/kds/pantallas/{aca['id']}",
        headers=h,
        json={"sucursal_id": ids["sucursal_b"]},
    )
    assert r.status_code == 409, r.text
    assert "Horno" in r.json()["detail"]


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


# --- Historial y corrección de la entrega (2026-08-26) -------------------------
def _historial(client, h, pantalla_id):
    return client.get(
        f"/api/v1/kds/pantallas/{pantalla_id}/historial", headers=h
    ).json()


def test_el_pedido_entregado_sale_de_la_cola_y_entra_al_historial(env):
    """Hasta ahora un pedido entregado desaparecía de la pantalla sin dejar
    dónde buscarlo: si se entregó el equivocado, no había forma de saberlo
    mirando la cocina."""
    client, ids = env
    h = _token(client)
    horno, barra, despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)

    assert _historial(client, h, despacho["id"]) == []
    client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)

    assert _cola(client, h, despacho["id"]) == []
    hist = _historial(client, h, despacho["id"])
    assert [p["venta_id"] for p in hist] == [venta["id"]]
    assert hist[0]["estado_pedido"] == "entregado"
    assert hist[0]["entregado_en"]


def test_el_historial_de_otra_sucursal_no_se_ve(env):
    client, ids = env
    h = _token(client)
    horno, barra, _despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)
    client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)

    ajena = client.post("/api/v1/kds/pantallas", headers=h, json={
        "sucursal_id": ids["sucursal_b"], "nombre": "Pase", "tipo": "despacho",
    }).json()
    assert _historial(client, h, ajena["id"]) == []


def test_deshacer_una_entrega_equivocada_devuelve_el_pedido_a_despacho(env):
    """El toque sobre la tarjeta de al lado. Sin vuelta, el único arreglo
    era anular la venta —que es otra cosa— o dejar la cocina mintiendo."""
    client, ids = env
    h = _token(client)
    horno, barra, despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)
    client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)

    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/deshacer-entrega", headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado_pedido"] == "listo"
    assert [p["venta_id"] for p in _cola(client, h, despacho["id"])] == [venta["id"]]
    assert _historial(client, h, despacho["id"]) == []


def test_deshacer_una_entrega_que_no_ocurrio_no_es_un_error(env):
    """Dos toques del mismo botón, o dos tablets mirando el mismo pedido: un
    409 acá no significaría nada para quien lo lee."""
    client, ids = env
    h = _token(client)
    horno, barra, _despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/deshacer-entrega", headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado_pedido"] == "listo"


def test_una_venta_anulada_no_tiene_entrega_que_deshacer(env):
    client, ids = env
    h = _token(client)
    horno, barra, _despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)
    client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)
    client.post(f"/api/v1/sales/ventas/{venta['id']}/anular", headers=h)
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/deshacer-entrega", headers=h
    ).status_code == 409


def test_la_cocina_no_deshace_una_entrega(env):
    """Mismo permiso que entregar (RN-CUP-006): el cocinero no da por
    entregado un pedido, y tampoco lo desentrega."""
    client, ids = env
    h = _token(client)
    horno, barra, _despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)
    client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)

    cocina = _token(client, "cocinero1", "111222")
    assert client.post(
        f"/api/v1/sales/ventas/{venta['id']}/deshacer-entrega", headers=cocina
    ).status_code == 403


def test_desde_el_kds_no_se_deshace_la_entrega(env):
    """`/retroceder` es de a un paso dentro de cocina; salir de `entregado`
    es un acto de la venta completa y tiene su propia puerta."""
    client, ids = env
    h = _token(client)
    horno, barra, _despacho, venta = _setup_pantallas_y_venta(client, ids, h)
    _dejar_pedido_listo(client, h, horno, barra)
    item = client.get(
        f"/api/v1/kds/ventas/{venta['id']}/avance", headers=h
    ).json()["items"][0]["venta_item_id"]
    client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)

    r = client.post(f"/api/v1/kds/items/{item}/retroceder", headers=h)
    assert r.status_code == 409, r.text
    assert "deshacer-entrega" in r.json()["detail"]


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


def test_la_linea_mandada_por_error_vuelve_a_la_estacion_anterior(env):
    """El error de envío que motivó todo esto: en armado se tacha la pizza
    antes de tiempo y se va al horno. Deshacer la trae de vuelta al armado,
    no la deja lista ni la manda al principio del pedido."""
    client, ids = env
    h = _token(client)
    armado, horno, _barra, _ = _cadena_de_tres(client, ids, h)
    pizza = _cola(client, h, armado["id"])[0]["items"][0]
    _tachar(client, h, pizza["venta_item_id"])
    assert _cola(client, h, armado["id"]) == []

    r = client.post(
        f"/api/v1/kds/items/{pizza['venta_item_id']}/retroceder", headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["etapa_kds"] == 0
    # Sigue en preparación: lo que se deshizo fue el envío, no el trabajo.
    assert r.json()["estado"] == "en_preparacion"

    devuelta = _cola(client, h, armado["id"])[0]["items"][0]
    assert devuelta["estacion"] == "Armado"
    assert _cola(client, h, horno["id"]) == []


def test_una_linea_lista_vuelve_a_su_ultima_estacion(env):
    """`listo` vuelve a `en_preparacion` en el eslabón donde se terminó —el
    horno—, no en el primero de la cadena: el armado ya hizo lo suyo."""
    client, ids = env
    h = _token(client)
    armado, horno, _barra, _ = _cadena_de_tres(client, ids, h)
    pizza = _cola(client, h, armado["id"])[0]["items"][0]["venta_item_id"]
    _tachar(client, h, pizza)
    _tachar(client, h, pizza, desde="en_preparacion")

    r = client.post(f"/api/v1/kds/items/{pizza}/retroceder", headers=h)
    assert r.json()["estado"] == "en_preparacion"
    assert r.json()["etapa_kds"] == 1
    assert _cola(client, h, horno["id"])[0]["items"][0]["estacion"] == "Horno"
    assert _cola(client, h, armado["id"]) == []


def test_la_bebida_vuelve_a_la_barra_y_no_al_horno(env):
    """La cadena de una línea son solo las estaciones que atienden su
    categoría: deshacer una bebida no puede mandarla a un horno por el que
    nunca pasó."""
    client, ids = env
    h = _token(client)
    _armado, horno, barra, _ = _cadena_de_tres(client, ids, h)
    bebida = _cola(client, h, barra["id"])[0]["items"][0]["venta_item_id"]
    _tachar(client, h, bebida)

    r = client.post(f"/api/v1/kds/items/{bebida}/retroceder", headers=h)
    assert r.json()["estado"] == "en_preparacion"
    assert r.json()["etapa_kds"] == 0
    assert _cola(client, h, barra["id"])[0]["items"][0]["estacion"] == "Barra"
    assert _cola(client, h, horno["id"]) == []


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
