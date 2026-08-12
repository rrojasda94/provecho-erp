"""Recetas editables, variantes de producto y grupos de opciones (ADR-023).

Cubre las tres promesas del slice:

- La cantidad de una línea de receta puede escribirse como operación
  ("1000/3") y se guarda redondeada a los decimales de la UdM del insumo,
  con la expresión al lado para poder reeditarla.
- Un producto con variantes no se vende: se vende la variante elegida, que
  lleva su propia receta y su propio precio completo (RN-COM-022).
- Un grupo de extras con `minimo >= 1` bloquea la venta hasta que se elija
  (RN-COM-023), y el tope del grupo se hace cumplir en el servidor.
"""

import uuid
from datetime import timedelta
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
    UnidadMedida,
)
from src.modules.sales.infrastructure.models import PuntoVenta
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Empresa, Grupo, Marca, Sucursal
from src.shared import fechas
from src.shared.aritmetica import ExpresionInvalida, evaluar, redondear
from src.shared.texto import a_titulo

AYER = fechas.hoy() - timedelta(days=1)


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
        cat_peso = CategoriaUdm(nombre="Peso")
        cat_unidad = CategoriaUdm(nombre="Cantidad")
        s.add_all([sucursal, cat_peso, cat_unidad])
        s.flush()
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador", serie_boleta="B001",
            serie_factura="F001", politica_pago="adelantado",
        )
        # Gramo con 3 decimales y Unidad con 0: el redondeo por línea tiene
        # que respetar la unidad de CADA insumo, no una regla global.
        gramo = UnidadMedida(categoria_udm_id=cat_peso.id, nombre="Gramo", decimales=3)
        unidad = UnidadMedida(
            categoria_udm_id=cat_unidad.id, nombre="Unidad", decimales=0
        )
        s.add_all([pv, gramo, unidad])
        s.flush()
        queso = Articulo(
            empresa_id=empresa.id, id_interno="QUES", nombre="Queso Mozzarella",
            unidad_medida_id=gramo.id, tipo="insumo", costo_promedio=Decimal("0.02"),
        )
        masa = Articulo(
            empresa_id=empresa.id, id_interno="MASA", nombre="Bollo de Masa",
            unidad_medida_id=unidad.id, tipo="insumo", costo_promedio=Decimal("1.50"),
        )
        s.add_all([queso, masa])
        s.flush()
        ids.update(
            sucursal_id=str(sucursal.id), pv_id=str(pv.id), marca_id=str(marca.id),
            gramo_id=str(gramo.id), unidad_id=str(unidad.id),
            queso_id=str(queso.id), masa_id=str(masa.id),
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


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _receta(client, h, ids, nombre="Base"):
    r = client.post("/api/v1/inventory/recetas", headers=h, json={
        "nombre": nombre, "rendimiento_cantidad": "1",
        "rendimiento_unidad_medida_id": ids["unidad_id"],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _producto(client, h, ids, **campos):
    body = {"marca_id": ids["marca_id"], **campos}
    return client.post("/api/v1/sales/productos", headers=h, json=body)


def _precio(client, h, ids, producto_id, monto, lista_id=None):
    if lista_id is None:
        r = client.post("/api/v1/sales/listas-precio", headers=h, json={
            "marca_id": ids["marca_id"], "nombre": "Carta", "vigente_desde": str(AYER),
        })
        assert r.status_code == 201, r.text
        lista_id = r.json()["id"]
    rp = client.post(f"/api/v1/sales/listas-precio/{lista_id}/precios", headers=h,
                     json={"producto_comercial_id": producto_id, "monto": str(monto)})
    assert rp.status_code == 201, rp.text
    return lista_id


# --- Utilidades puras -------------------------------------------------------
def test_formato_titulo_respeta_conectores_y_siglas():
    assert a_titulo("pizza de peperoni familiar") == "Pizza de Peperoni Familiar"
    assert a_titulo("QUESO MOZZARELLA") == "Queso Mozzarella"
    assert a_titulo("pizza XL") == "Pizza XL"
    assert a_titulo("coca-cola sin azúcar") == "Coca-Cola sin Azúcar"
    assert a_titulo("  doble   espacio ") == "Doble Espacio"
    assert a_titulo(None) is None


def test_aritmetica_evalua_y_redondea_por_unidad():
    assert evaluar("1000/3") == Decimal(1000) / Decimal(3)
    assert redondear(evaluar("1000/3"), 3) == Decimal("333.333")
    assert redondear(evaluar("1000/3"), 0) == Decimal("333")
    assert evaluar("(80+20)*2.5") == Decimal("250")
    with pytest.raises(ExpresionInvalida):
        evaluar("__import__('os').system('ls')")
    with pytest.raises(ExpresionInvalida):
        evaluar("1/0")


# --- Recetas ----------------------------------------------------------------
def test_linea_con_operacion_guarda_resultado_redondeado_y_expresion(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids)

    r = client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h, json={
        "articulo_id": ids["queso_id"], "expresion": "1000/3",
    })
    assert r.status_code == 201, r.text
    item = r.json()["items"][0]
    # Gramo declara 3 decimales: ni más (la columna no los guarda) ni menos.
    assert Decimal(item["cantidad"]) == Decimal("333.333")
    assert item["expresion"] == "1000/3"
    assert item["unidad_medida_nombre"] == "Gramo"


def test_la_unidad_del_insumo_manda_en_el_redondeo(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids)

    # Misma operación, otro insumo: la Unidad no admite decimales, media
    # bollo de masa no existe.
    r = client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h, json={
        "articulo_id": ids["masa_id"], "expresion": "3/2",
    })
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["items"][0]["cantidad"]) == Decimal(2)


def test_expresion_invalida_no_se_evalua(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids)
    r = client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h, json={
        "articulo_id": ids["queso_id"], "expresion": "open('x')",
    })
    # 409 y no 500: `ExpresionInvalida` es una regla de negocio, no un bug.
    assert r.status_code == 409, r.text


def test_duplicar_agrega_copy_y_clona_las_lineas(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids, nombre="Pizza Personal")
    client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h, json={
        "articulo_id": ids["queso_id"], "cantidad": "180",
    })

    r = client.post(f"/api/v1/inventory/recetas/{receta_id}/duplicar", headers=h)
    assert r.status_code == 201, r.text
    copia = r.json()
    assert copia["nombre"] == "Pizza Personal (copy)"
    assert len(copia["items"]) == 1

    # Duplicar dos veces no puede chocar con el nombre ya tomado.
    segunda = client.post(f"/api/v1/inventory/recetas/{receta_id}/duplicar", headers=h)
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["nombre"] == "Pizza Personal (copy) 2"

    # Duplicar una copia NO apila el sufijo: "(copy) (copy)" no le dice nada
    # a nadie y a la tercera el nombre ya es ilegible.
    tercera = client.post(
        f"/api/v1/inventory/recetas/{copia['id']}/duplicar", headers=h
    )
    assert tercera.status_code == 201, tercera.text
    assert tercera.json()["nombre"] == "Pizza Personal (copy) 3"


def test_nombre_de_articulo_y_categoria_tambien_van_en_formato_titulo(env):
    client, ids = env
    h = _token(client)
    cat = client.post("/api/v1/inventory/categorias", headers=h,
                      json={"nombre": "insumos de cocina"})
    assert cat.status_code == 201, cat.text
    assert cat.json()["nombre"] == "Insumos de Cocina"

    art = client.post("/api/v1/inventory/articulos", headers=h, json={
        "id_interno": "MSPZ", "nombre": "masa de pizza",
        "unidad_medida_id": ids["unidad_id"], "tipo": "subreceta",
    })
    assert art.status_code == 201, art.text
    assert art.json()["nombre"] == "Masa de Pizza"

    editado = client.patch(f"/api/v1/inventory/articulos/{art.json()['id']}",
                           headers=h, json={"nombre": "masa de pizza integral"})
    assert editado.status_code == 200, editado.text
    assert editado.json()["nombre"] == "Masa de Pizza Integral"


def test_receta_declara_la_subreceta_que_produce(env):
    client, ids = env
    h = _token(client)
    art = client.post("/api/v1/inventory/articulos", headers=h, json={
        "id_interno": "SALS", "nombre": "Salsa de Tomate",
        "unidad_medida_id": ids["unidad_id"], "tipo": "subreceta",
    }).json()
    receta_id = _receta(client, h, ids, nombre="Salsa de Tomate Casera")

    r = client.patch(f"/api/v1/inventory/recetas/{receta_id}", headers=h,
                     json={"articulo_id": art["id"]})
    assert r.status_code == 200, r.text
    assert str(r.json()["articulo_id"]) == art["id"]

    # Dos recetas produciendo el mismo artículo dejarían a producción sin
    # saber cuál explotar.
    otra = _receta(client, h, ids, nombre="Salsa de Tomate Rápida")
    choque = client.patch(f"/api/v1/inventory/recetas/{otra}", headers=h,
                          json={"articulo_id": art["id"]})
    assert choque.status_code == 409, choque.text


def test_renombrar_receta_y_cambiar_su_rendimiento(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids, nombre="Pizza Personal")
    copia = client.post(
        f"/api/v1/inventory/recetas/{receta_id}/duplicar", headers=h
    ).json()

    # Sin esto, duplicar no sirve de nada: la copia queda llamándose "(copy)"
    # para siempre.
    r = client.patch(
        f"/api/v1/inventory/recetas/{copia['id']}", headers=h,
        json={"nombre": "pizza peperoni familiar", "rendimiento_cantidad": "2"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Pizza Peperoni Familiar"
    assert Decimal(r.json()["rendimiento_cantidad"]) == Decimal(2)

    # Dos recetas con el mismo nombre volverían ambiguo el selector.
    choque = client.patch(
        f"/api/v1/inventory/recetas/{copia['id']}", headers=h,
        json={"nombre": "Pizza Personal"},
    )
    assert choque.status_code == 409, choque.text


def test_escalar_redondea_cada_linea_con_su_propia_unidad(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids)
    client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h,
                json={"articulo_id": ids["queso_id"], "cantidad": "180"})
    client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h,
                json={"articulo_id": ids["masa_id"], "cantidad": "1"})

    r = client.post(f"/api/v1/inventory/recetas/{receta_id}/escalar", headers=h,
                    json={"factor": "1.5"})
    assert r.status_code == 200, r.text
    por_articulo = {i["articulo_id"]: i for i in r.json()["items"]}
    assert Decimal(por_articulo[ids["queso_id"]]["cantidad"]) == Decimal("270")
    # 1 bollo × 1.5 = 1.5 → 2, porque la Unidad no tiene decimales.
    assert Decimal(por_articulo[ids["masa_id"]]["cantidad"]) == Decimal(2)
    assert por_articulo[ids["queso_id"]]["expresion"] == "(180)*1.5"


def test_el_insumo_no_puede_ser_lo_que_la_receta_produce(env):
    client, ids = env
    h = _token(client)
    r = client.post("/api/v1/inventory/recetas", headers=h, json={
        "nombre": "Salsa Base", "rendimiento_cantidad": "1",
        "rendimiento_unidad_medida_id": ids["unidad_id"],
        "articulo_id": ids["masa_id"],
    })
    assert r.status_code == 201, r.text
    receta_id = r.json()["id"]

    mal = client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h,
                      json={"articulo_id": ids["masa_id"], "cantidad": "1"})
    assert mal.status_code == 409, mal.text


# --- Variantes --------------------------------------------------------------
def test_producto_con_variantes_no_se_vende_pero_la_variante_si(env):
    client, ids = env
    h = _token(client)
    padre = _producto(client, h, ids, id_interno="PZPE", nombre="pizza de peperoni")
    assert padre.status_code == 201, padre.text
    padre_id = padre.json()["id"]
    # El nombre se normaliza en el servidor, no solo en la pantalla.
    assert padre.json()["nombre"] == "Pizza de Peperoni"

    receta_id = _receta(client, h, ids, nombre="Pizza Peperoni Familiar")
    variante = _producto(client, h, ids, id_interno="PZPF", nombre="Familiar",
                         receta_id=receta_id, producto_padre_id=padre_id, orden=3)
    assert variante.status_code == 201, variante.text
    variante_id = variante.json()["id"]

    lista_id = _precio(client, h, ids, variante_id, "45.00")
    # El padre no puede tener precio: lo que se cobra sale de la variante.
    mal_precio = client.post(
        f"/api/v1/sales/listas-precio/{lista_id}/precios", headers=h,
        json={"producto_comercial_id": padre_id, "monto": "40.00"},
    )
    assert mal_precio.status_code == 409, mal_precio.text

    def vender(producto_id, key):
        return client.post("/api/v1/sales/ventas", headers=h, json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": key,
            "items": [{"producto_comercial_id": producto_id, "cantidad": "1"}],
        })

    assert vender(padre_id, "padre-01").status_code == 409
    assert vender(variante_id, "variante-01").status_code == 201

    # La ficha trae padre + variantes en una sola lectura: es lo que edita
    # la pantalla de catálogo sin salir a otra vista.
    ficha = client.get(f"/api/v1/sales/productos/{padre_id}", headers=h)
    assert ficha.status_code == 200, ficha.text
    assert ficha.json()["receta_id"] is None
    assert [v["nombre"] for v in ficha.json()["variantes"]] == ["Familiar"]


def test_la_carta_muestra_variantes_dentro_del_padre(env):
    client, ids = env
    h = _token(client)
    padre_id = _producto(
        client, h, ids, id_interno="PZPE", nombre="Pizza de Peperoni"
    ).json()["id"]
    lista_id = None
    for codigo, nombre, monto, orden in (
        ("PZPP", "Personal", "18.00", 1),
        ("PZPF", "Familiar", "45.00", 3),
    ):
        receta_id = _receta(client, h, ids, nombre=f"Pizza Peperoni {nombre}")
        variante_id = _producto(
            client, h, ids, id_interno=codigo, nombre=nombre, receta_id=receta_id,
            producto_padre_id=padre_id, orden=orden,
        ).json()["id"]
        lista_id = _precio(client, h, ids, variante_id, monto, lista_id)

    r = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    )
    assert r.status_code == 200, r.text
    items = r.json()
    # Las variantes no salen sueltas en la grilla: solo el padre.
    assert [i["producto_comercial_id"] for i in items] == [padre_id]
    carta = items[0]
    assert [v["nombre"] for v in carta["variantes"]] == ["Personal", "Familiar"]
    # El precio de la tarjeta es el "desde", el de la variante más barata.
    assert Decimal(carta["precio_unitario"]) == Decimal("18.00")


def test_una_variante_no_admite_variantes_propias(env):
    client, ids = env
    h = _token(client)
    padre_id = _producto(client, h, ids, id_interno="PZPE", nombre="Pizza").json()["id"]
    receta_id = _receta(client, h, ids, nombre="Pizza Familiar")
    variante_id = _producto(client, h, ids, id_interno="PZPF", nombre="Familiar",
                            receta_id=receta_id, producto_padre_id=padre_id).json()["id"]

    otra = _receta(client, h, ids, nombre="Pizza Familiar Con Borde")
    r = _producto(client, h, ids, id_interno="PZPB", nombre="Con Borde",
                  receta_id=otra, producto_padre_id=variante_id)
    assert r.status_code == 409, r.text


def test_quitar_la_receta_convierte_el_producto_en_uno_con_presentaciones(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids, nombre="Pizza Simple")
    producto_id = _producto(client, h, ids, id_interno="PZSI", nombre="Pizza",
                            receta_id=receta_id).json()["id"]

    # Con receta propia el producto se vende tal cual: no admite presentaciones.
    otra = _receta(client, h, ids, nombre="Pizza Familiar")
    bloqueado = _producto(client, h, ids, id_interno="PZFA", nombre="Familiar",
                          receta_id=otra, producto_padre_id=producto_id)
    assert bloqueado.status_code == 409, bloqueado.text

    r = client.patch(f"/api/v1/sales/productos/{producto_id}", headers=h,
                     json={"quitar_receta": True})
    assert r.status_code == 200, r.text
    assert r.json()["receta_id"] is None

    # La receta soltada sigue existiendo, lista para la primera presentación.
    assert client.get(f"/api/v1/inventory/recetas/{receta_id}",
                      headers=h).status_code == 200
    ahora = _producto(client, h, ids, id_interno="PZFA", nombre="Familiar",
                      receta_id=otra, producto_padre_id=producto_id)
    assert ahora.status_code == 201, ahora.text


def test_una_presentacion_no_puede_quedarse_sin_receta(env):
    client, ids = env
    h = _token(client)
    padre_id = _producto(client, h, ids, id_interno="PZPE", nombre="Pizza").json()["id"]
    variante_id = _producto(
        client, h, ids, id_interno="PZPF", nombre="Familiar",
        receta_id=_receta(client, h, ids, nombre="Pizza Familiar"),
        producto_padre_id=padre_id,
    ).json()["id"]

    r = client.patch(f"/api/v1/sales/productos/{variante_id}", headers=h,
                     json={"quitar_receta": True})
    assert r.status_code == 409, r.text


def test_borrar_presentacion_solo_si_nunca_se_vendio(env):
    client, ids = env
    h = _token(client)
    padre_id = _producto(client, h, ids, id_interno="PZPE", nombre="Pizza").json()["id"]
    variante_id = _producto(
        client, h, ids, id_interno="PZPF", nombre="Familiar",
        receta_id=_receta(client, h, ids, nombre="Pizza Familiar"),
        producto_padre_id=padre_id,
    ).json()["id"]
    _precio(client, h, ids, variante_id, "45.00")

    # Sin ventas se borra, con precio y todo: ese precio solo existía por él.
    assert client.delete(f"/api/v1/sales/productos/{variante_id}",
                         headers=h).status_code == 204
    assert client.get(f"/api/v1/sales/productos/{variante_id}",
                      headers=h).status_code == 404

    # Con una venta encima ya no: reescribiría lo que se cobró.
    otra_id = _producto(
        client, h, ids, id_interno="PZPP", nombre="Personal",
        receta_id=_receta(client, h, ids, nombre="Pizza Personal"),
        producto_padre_id=padre_id,
    ).json()["id"]
    _precio(client, h, ids, otra_id, "18.00")
    venta = client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "takeout", "idempotency_key": str(uuid.uuid4()),
        "items": [{"producto_comercial_id": otra_id, "cantidad": "1"}],
    })
    assert venta.status_code == 201, venta.text
    vendido = client.delete(f"/api/v1/sales/productos/{otra_id}", headers=h)
    assert vendido.status_code == 409, vendido.text
    assert "descontinúa" in vendido.json()["detail"]


def test_borrar_receta_solo_si_ningun_producto_la_usa(env):
    client, ids = env
    h = _token(client)
    receta_id = _receta(client, h, ids, nombre="Salsa Base")
    client.post(f"/api/v1/inventory/recetas/{receta_id}/items", headers=h,
                json={"articulo_id": ids["queso_id"], "cantidad": "100"})
    producto_id = _producto(client, h, ids, id_interno="PZSB", nombre="Pizza Base",
                            receta_id=receta_id).json()["id"]

    en_uso = client.delete(f"/api/v1/inventory/recetas/{receta_id}", headers=h)
    assert en_uso.status_code == 409, en_uso.text
    # El mensaje nombra al producto: "clave foránea" no le dice nada a nadie.
    assert "Pizza Base" in en_uso.json()["detail"]

    otra = _receta(client, h, ids, nombre="Salsa Nueva")
    client.patch(f"/api/v1/sales/productos/{producto_id}", headers=h,
                 json={"receta_id": otra})
    assert client.delete(f"/api/v1/inventory/recetas/{receta_id}",
                         headers=h).status_code == 204
    assert client.get(f"/api/v1/inventory/recetas/{receta_id}",
                      headers=h).status_code == 404


# --- Grupos de opciones -----------------------------------------------------
def test_grupo_obligatorio_bloquea_la_venta_hasta_elegir(env):
    client, ids = env
    h = _token(client)
    receta_pizza = _receta(client, h, ids, nombre="Pizza Simple")
    producto_id = _producto(client, h, ids, id_interno="PZSI", nombre="Pizza Simple",
                            receta_id=receta_pizza).json()["id"]
    receta_salsa = _receta(client, h, ids, nombre="Salsa BBQ")
    extra_id = _producto(client, h, ids, id_interno="SBBQ", nombre="Salsa BBQ",
                         receta_id=receta_salsa, es_extra=True).json()["id"]

    lista_id = _precio(client, h, ids, producto_id, "25.00")
    _precio(client, h, ids, extra_id, "2.00", lista_id)

    grupo = client.post(f"/api/v1/sales/productos/{producto_id}/grupos", headers=h,
                        json={"nombre": "Salsas", "minimo": 1, "maximo": 1})
    assert grupo.status_code == 201, grupo.text
    grupo_id = grupo.json()["id"]
    vinculo = client.post(f"/api/v1/sales/productos/{producto_id}/extras", headers=h,
                          json={"extra_id": extra_id, "grupo_id": grupo_id})
    assert vinculo.status_code == 201, vinculo.text

    def vender(extras, key):
        return client.post("/api/v1/sales/ventas", headers=h, json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": key,
            "items": [{
                "producto_comercial_id": producto_id, "cantidad": "1",
                "extras": extras,
            }],
        })

    sin_elegir = vender([], "grupo-01")
    assert sin_elegir.status_code == 409, sin_elegir.text
    assert "Salsas" in sin_elegir.json()["detail"]

    eligiendo = vender(
        [{"producto_comercial_id": extra_id, "cantidad": "1"}], "grupo-02"
    )
    assert eligiendo.status_code == 201, eligiendo.text

    # La carta le dice al PDV qué grupo obliga y con qué mínimo.
    carta = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    ).json()
    extra_en_carta = carta[0]["extras"][0]
    assert extra_en_carta["grupo_nombre"] == "Salsas"
    assert extra_en_carta["grupo_minimo"] == 1


def test_extra_sin_grupo_sigue_siendo_opcional(env):
    client, ids = env
    h = _token(client)
    receta_pizza = _receta(client, h, ids, nombre="Pizza Suelta")
    producto_id = _producto(client, h, ids, id_interno="PZSU", nombre="Pizza Suelta",
                            receta_id=receta_pizza).json()["id"]
    receta_queso = _receta(client, h, ids, nombre="Extra Queso")
    extra_id = _producto(client, h, ids, id_interno="EXQU", nombre="Extra Queso",
                         receta_id=receta_queso, es_extra=True).json()["id"]
    lista_id = _precio(client, h, ids, producto_id, "25.00")
    _precio(client, h, ids, extra_id, "3.00", lista_id)
    client.post(f"/api/v1/sales/productos/{producto_id}/extras", headers=h,
                json={"extra_id": extra_id})

    r = client.post("/api/v1/sales/ventas", headers=h, json={
        "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
        "canal": "pdv", "modalidad": "takeout",
        "idempotency_key": str(uuid.uuid4()),
        "items": [{"producto_comercial_id": producto_id, "cantidad": "1"}],
    })
    assert r.status_code == 201, r.text


def test_la_carta_trae_los_grupos_de_cada_variante(env):
    """El caso real: los sabores cuelgan del TAMAÑO, no del padre.

    Los otros dos casos de grupo usan un producto sin presentaciones, donde
    el grupo vive en el propio producto y la carta lo encontraba igual. Con
    variantes la carta leía los grupos del padre —que no tiene ninguno—, así
    que el PDV no dibujaba "Sabor", dejaba confirmar sin elegir y el servidor
    devolvía 409 por algo que la pantalla nunca ofreció.
    """
    client, ids = env
    h = _token(client)
    padre_id = _producto(client, h, ids, id_interno="PZVA", nombre="Pizza").json()["id"]
    variante_id = _producto(
        client, h, ids, id_interno="PZVP", nombre="Pizza Personal",
        receta_id=_receta(client, h, ids, nombre="Base Personal"),
        producto_padre_id=padre_id,
    ).json()["id"]
    sabor_id = _producto(
        client, h, ids, id_interno="SPEP", nombre="Peperoni",
        receta_id=_receta(client, h, ids, nombre="Sabor Peperoni"), es_extra=True,
    ).json()["id"]

    lista_id = _precio(client, h, ids, variante_id, "25.00")
    # El sabor no cobra aparte, pero sin precio de lista la carta lo descarta.
    _precio(client, h, ids, sabor_id, "0.00", lista_id)

    grupo_id = client.post(
        f"/api/v1/sales/productos/{variante_id}/grupos", headers=h,
        json={"nombre": "Sabor", "minimo": 1, "maximo": 1},
    ).json()["id"]
    assert client.post(
        f"/api/v1/sales/productos/{variante_id}/extras", headers=h,
        json={"extra_id": sabor_id, "grupo_id": grupo_id},
    ).status_code == 201

    carta = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    ).json()
    tarjeta = next(i for i in carta if i["producto_comercial_id"] == padre_id)
    # El padre no ofrece nada por su cuenta: lo suyo es agrupar tamaños.
    assert tarjeta["extras"] == []
    variante = tarjeta["variantes"][0]
    assert variante["producto_comercial_id"] == variante_id
    assert [e["nombre"] for e in variante["extras"]] == ["Peperoni"]
    assert variante["extras"][0]["grupo_nombre"] == "Sabor"
    assert variante["extras"][0]["grupo_minimo"] == 1

    # Y lo que la carta ofrece es exactamente lo que el servidor acepta.
    def vender(extras, key):
        return client.post("/api/v1/sales/ventas", headers=h, json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": key,
            "items": [{
                "producto_comercial_id": variante_id, "cantidad": "1",
                "extras": extras,
            }],
        })

    sin_sabor = vender([], "variante-01")
    assert sin_sabor.status_code == 409, sin_sabor.text
    assert "Sabor" in sin_sabor.json()["detail"]
    con_sabor = vender(
        [{"producto_comercial_id": sabor_id, "cantidad": "1"}], "variante-02"
    )
    assert con_sabor.status_code == 201, con_sabor.text


def test_la_variante_hereda_los_grupos_del_padre(env):
    """El caso que rompía en la operación real (ADR-042).

    El seeder cuelga el grupo de la variante; el lienzo lo cuelga del **padre**
    —"+ grupo" va al nodo activo, que es el padre mientras el producto no
    tiene tamaños—. Con la herencia, de dónde quedó colgado deja de decidir si
    la carta lo muestra y si la venta lo acepta.
    """
    client, ids = env
    h = _token(client)
    padre_id = _producto(client, h, ids, id_interno="PZHE", nombre="Pizza").json()["id"]
    sabor_id = _producto(
        client, h, ids, id_interno="SHAW", nombre="Hawaiana",
        receta_id=_receta(client, h, ids, nombre="Sabor Hawaiana"), es_extra=True,
    ).json()["id"]

    # El grupo y el extra cuelgan del PADRE, como los deja el lienzo.
    grupo_id = client.post(
        f"/api/v1/sales/productos/{padre_id}/grupos", headers=h,
        json={"nombre": "Sabor", "minimo": 1, "maximo": 1},
    ).json()["id"]
    assert client.post(
        f"/api/v1/sales/productos/{padre_id}/extras", headers=h,
        json={"extra_id": sabor_id, "grupo_id": grupo_id},
    ).status_code == 201

    # Y recién después se agrega el tamaño.
    variante_id = _producto(
        client, h, ids, id_interno="PZHP", nombre="Pizza Personal",
        receta_id=_receta(client, h, ids, nombre="Base Personal"),
        producto_padre_id=padre_id,
    ).json()["id"]
    lista_id = _precio(client, h, ids, variante_id, "25.00")
    _precio(client, h, ids, sabor_id, "0.00", lista_id)

    carta = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    ).json()
    variante = next(
        i for i in carta if i["producto_comercial_id"] == padre_id
    )["variantes"][0]
    assert [e["nombre"] for e in variante["extras"]] == ["Hawaiana"]
    assert variante["extras"][0]["grupo_minimo"] == 1

    def vender(extras, key):
        return client.post("/api/v1/sales/ventas", headers=h, json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": key,
            "items": [{
                "producto_comercial_id": variante_id, "cantidad": "1",
                "extras": extras,
            }],
        })

    # El grupo heredado obliga igual...
    sin_sabor = vender([], "hered-01")
    assert sin_sabor.status_code == 409, sin_sabor.text
    assert "Sabor" in sin_sabor.json()["detail"]
    # ...y el extra heredado se acepta: es el que la carta acaba de ofrecer.
    con_sabor = vender(
        [{"producto_comercial_id": sabor_id, "cantidad": "1"}], "hered-02"
    )
    assert con_sabor.status_code == 201, con_sabor.text


def test_lo_propio_de_la_variante_gana_sobre_lo_heredado(env):
    """Un tamaño puede acotar lo que el padre ofrece: si la familiar declara
    su propio vínculo, manda el suyo — es el más específico."""
    client, ids = env
    h = _token(client)
    padre_id = _producto(client, h, ids, id_interno="PZG2", nombre="Pizza Dos").json()["id"]
    extra_id = _producto(
        client, h, ids, id_interno="EXQ2", nombre="Extra Queso",
        receta_id=_receta(client, h, ids, nombre="Queso Extra"), es_extra=True,
    ).json()["id"]
    variante_id = _producto(
        client, h, ids, id_interno="PZ2F", nombre="Pizza Dos Familiar",
        receta_id=_receta(client, h, ids, nombre="Base Familiar Dos"),
        producto_padre_id=padre_id,
    ).json()["id"]

    # El padre lo ofrece sin tope; la familiar lo acota a 1.
    client.post(f"/api/v1/sales/productos/{padre_id}/extras", headers=h,
                json={"extra_id": extra_id, "maximo": 5})
    client.post(f"/api/v1/sales/productos/{variante_id}/extras", headers=h,
                json={"extra_id": extra_id, "maximo": 1})

    lista_id = _precio(client, h, ids, variante_id, "45.00")
    _precio(client, h, ids, extra_id, "6.00", lista_id)

    carta = client.get(
        f"/api/v1/sales/carta?sucursal_id={ids['sucursal_id']}"
        "&canal=pdv&modalidad=takeout",
        headers=h,
    ).json()
    variante = next(
        i for i in carta if i["producto_comercial_id"] == padre_id
    )["variantes"][0]
    # Una sola vez y con el tope de la variante, no dos filas del mismo extra.
    assert len(variante["extras"]) == 1
    assert variante["extras"][0]["maximo"] == 1
