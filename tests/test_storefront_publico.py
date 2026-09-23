"""Superficie pública del sitio de marca (`/storefront/publico/*`,
ADR-103): forma de la respuesta, RN-WEB-001 (nada de lo privado sale),
RN-WEB-002/003/004 (qué se filtra) y el rate limit por IP.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.database import Base
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    UnidadMedida,
)
from src.modules.rrhh.infrastructure.models import Convocatoria
from src.modules.sales.infrastructure.models import ProductoComercial, Promocion
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Empresa, Grupo, Marca, Sucursal

PUBLICO = "/api/v1/storefront/publico"

HOY = date.today()


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))

        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Centro",
            direccion="Jr. X 123", telefono="972510528", tenencia="alquilada",
            estado="activa", horario_atencion={"lun": [["11:00", "23:00"]]},
        )
        s.add(sucursal)
        s.flush()

        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
        s.add(udm)
        s.flush()

        insumo = Articulo(
            empresa_id=empresa.id, id_interno="ART0001", nombre="Queso mozzarella",
            descripcion="Queso mozzarella fresco", unidad_medida_id=udm.id, tipo="insumo",
        )
        s.add(insumo)
        s.flush()

        receta = Receta(
            empresa_id=empresa.id, nombre="Pizza clasica",
            rendimiento_cantidad=Decimal(1), rendimiento_unidad_medida_id=udm.id,
        )
        s.add(receta)
        s.flush()
        s.add(
            RecetaItem(
                receta_id=receta.id, articulo_id=insumo.id, cantidad=Decimal("0.2"),
            )
        )

        producto = ProductoComercial(
            id_interno="P0000001", marca_id=marca.id, nombre="Pizza Clasica",
            descripcion="La receta de siempre", receta_id=receta.id,
        )
        s.add(producto)
        s.flush()

        ids.update(
            empresa_id=str(empresa.id), grupo_id=str(grupo.id), marca_id=str(marca.id),
            sucursal_id=str(sucursal.id), producto_id=str(producto.id),
            insumo_id=str(insumo.id),
        )
        s.commit()

    monkeypatch.setattr(settings, "storefront_marca_id", ids["marca_id"])
    monkeypatch.setattr(settings, "storefront_sucursal_id", ids["sucursal_id"])
    monkeypatch.setattr(settings, "storefront_canal", "delivery")
    monkeypatch.setattr(settings, "storefront_modalidad", "delivery")

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


def _token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_lista_y_precio(client, headers, ids, monto="35.00"):
    body = {
        "marca_id": ids["marca_id"], "nombre": "Lista delivery",
        "vigente_desde": str(HOY - timedelta(days=1)),
        "canal": "delivery", "modalidad": "delivery",
    }
    r = client.post("/api/v1/sales/listas-precio", headers=headers, json=body)
    assert r.status_code == 201, r.text
    lista_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/sales/listas-precio/{lista_id}/precios", headers=headers,
        json={"producto_comercial_id": ids["producto_id"], "monto": monto},
    )
    assert r2.status_code == 201, r2.text


def test_sitio_no_configurado_responde_404(env, monkeypatch):
    client, ids, _ = env
    monkeypatch.setattr(settings, "storefront_marca_id", "")
    r = client.get(f"{PUBLICO}/contenido")
    assert r.status_code == 404


def test_contenido_publico_trae_lo_sembrado(env):
    client, ids, _ = env
    r = client.get(f"{PUBLICO}/contenido")
    assert r.status_code == 200
    body = r.json()
    assert body["marca"]["nombre"] == "Charlie's Pizzas"
    assert "hero" in body["contenido"]
    assert body["contenido"]["hero"]["titulo"]
    assert r.headers["cache-control"] == "public, max-age=60"


def test_carta_trae_producto_con_ingredientes_y_sin_campos_prohibidos(env):
    client, ids, _ = env
    headers = _token(client)
    _crear_lista_y_precio(client, headers, ids)

    r = client.get(f"{PUBLICO}/carta")
    assert r.status_code == 200
    body = r.json()
    assert len(body["productos"]) == 1
    producto = body["productos"][0]
    assert producto["nombre"] == "Pizza Clasica"
    assert producto["descripcion"] == "La receta de siempre"
    assert Decimal(producto["precio_desde"]) == Decimal("35.00")
    assert producto["disponible"] is True
    assert [i["nombre"] for i in producto["ingredientes"]] == ["Queso mozzarella"]

    crudo = r.text
    for prohibido in ("empresa_id", "grupo_id", "costo_promedio", "margen_contribucion"):
        assert prohibido not in crudo, prohibido + " se filtro a la carta publica"



def test_un_producto_con_tamanos_lista_los_ingredientes_de_sus_variantes(env):
    """La receta vive en la variante, nunca en el padre.

    `catalogo.crear_variante` **obliga** a que un producto con tamaños no
    tenga receta propia, así que el nodo padre llegaba siempre con
    `ingredientes: []` y en el sitio ninguna pizza con tamaños mostraba un
    solo ingrediente. El fixture de las otras pruebas no tiene variantes, que
    es por lo que esto pasó en verde hasta verlo en el sitio real.
    """
    from src.modules.inventory.infrastructure.models import Receta, RecetaItem, UnidadMedida

    client, ids, TestSession = env
    headers = _token(client)
    with TestSession() as s:
        padre = s.get(ProductoComercial, uuid.UUID(ids["producto_id"]))
        udm_id = s.scalar(select(UnidadMedida.id))
        albahaca = Articulo(
            empresa_id=uuid.UUID(ids["empresa_id"]), id_interno="ART0002",
            nombre="ALBAHACA FRESCA X 100G", nombre_publico="Albahaca",
            unidad_medida_id=udm_id, tipo="insumo",
        )
        s.add(albahaca)
        s.flush()
        receta_grande = Receta(
            empresa_id=uuid.UUID(ids["empresa_id"]), nombre="Pizza clasica familiar",
            rendimiento_cantidad=Decimal(1), rendimiento_unidad_medida_id=udm_id,
        )
        s.add(receta_grande)
        s.flush()
        s.add_all([
            RecetaItem(
                receta_id=receta_grande.id, articulo_id=uuid.UUID(ids["insumo_id"]),
                cantidad=Decimal("0.4"),
            ),
            RecetaItem(
                receta_id=receta_grande.id, articulo_id=albahaca.id, cantidad=Decimal("0.01"),
            ),
        ])
        # El padre pierde su receta y gana una variante que sí la tiene, que es
        # la forma en la que el ERP guarda una pizza con tamaños.
        receta_del_padre = padre.receta_id
        padre.receta_id = None
        variante = ProductoComercial(
            id_interno="P0000002", marca_id=uuid.UUID(ids["marca_id"]),
            nombre="Pizza Clasica Familiar", producto_padre_id=padre.id,
            receta_id=receta_grande.id,
        )
        s.add(variante)
        s.flush()
        assert receta_del_padre is not None
        variante_id = str(variante.id)
        s.commit()

    # El precio va en la variante: un producto con variantes no se vende por
    # sí mismo (RN-COM-022).
    r = client.post(
        "/api/v1/sales/listas-precio", headers=headers,
        json={
            "marca_id": ids["marca_id"], "nombre": "Lista delivery",
            "vigente_desde": str(HOY - timedelta(days=1)),
            "canal": "delivery", "modalidad": "delivery",
        },
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"/api/v1/sales/listas-precio/{r.json()['id']}/precios", headers=headers,
        json={"producto_comercial_id": variante_id, "monto": "60.00"},
    )
    assert r.status_code == 201, r.text

    producto = client.get(f"{PUBLICO}/carta").json()["productos"][0]
    nombres = [i["nombre"] for i in producto["ingredientes"]]
    # Los de la variante, y el alias en vez del nombre de almacén.
    assert nombres == ["Albahaca", "Queso mozzarella"]

    detalle = client.get(f"{PUBLICO}/productos/{ids['producto_id']}").json()
    assert [i["nombre"] for i in detalle["ingredientes_detalle"]] == [
        "Albahaca", "Queso mozzarella",
    ]


def test_las_categorias_de_la_carta_traen_su_nombre(env):
    """Sin nombre, los chips de categoría del sitio salían como puntos vacíos."""
    from src.modules.inventory.infrastructure.models import Categoria

    client, ids, TestSession = env
    with TestSession() as s:
        categoria = Categoria(empresa_id=uuid.UUID(ids["empresa_id"]), nombre="Pizzas")
        s.add(categoria)
        s.flush()
        producto = s.get(ProductoComercial, uuid.UUID(ids["producto_id"]))
        producto.categoria_id = categoria.id
        s.commit()
        categoria_id = str(categoria.id)

    _crear_lista_y_precio(client, _token(client), ids)
    body = client.get(f"{PUBLICO}/carta").json()
    assert body["categorias"] == [{"id": categoria_id, "nombre": "Pizzas"}]
    assert body["productos"][0]["categoria_id"] == categoria_id


def test_detalle_de_producto_trae_ingrediente_con_descripcion_y_foto_null(env):
    client, ids, _ = env
    headers = _token(client)
    _crear_lista_y_precio(client, headers, ids)

    r = client.get(f"{PUBLICO}/productos/{ids['producto_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["ingredientes_detalle"][0]["nombre"] == "Queso mozzarella"
    assert body["ingredientes_detalle"][0]["descripcion"] == "Queso mozzarella fresco"
    assert body["ingredientes_detalle"][0]["foto_url"] is None
    assert body["fotos"] == []


def test_producto_inexistente_404(env):
    client, ids, _ = env
    r = client.get(f"{PUBLICO}/productos/{uuid.uuid4()}")
    assert r.status_code == 404


def test_ingrediente_publico(env):
    client, ids, _ = env
    r = client.get(f"{PUBLICO}/ingredientes/{ids['insumo_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["nombre"] == "Queso mozzarella"
    assert body["descripcion"] == "Queso mozzarella fresco"


def test_sucursales_solo_activas_de_la_marca(env, monkeypatch):
    client, ids, TestSession = env
    with TestSession() as s:
        marca = s.get(Marca, uuid.UUID(ids["marca_id"]))
        cerrada = Sucursal(
            marca_id=marca.id, empresa_id=uuid.UUID(ids["empresa_id"]), nombre="Cerrada",
            direccion="Jr. Y 456", tenencia="alquilada", estado="inactiva",
        )
        s.add(cerrada)
        s.commit()

    r = client.get(f"{PUBLICO}/sucursales")
    assert r.status_code == 200
    nombres = [s["nombre"] for s in r.json()]
    assert "Centro" in nombres
    assert "Cerrada" not in nombres
    centro = next(s for s in r.json() if s["nombre"] == "Centro")
    assert centro["telefono"] == "972510528"


def test_promocion_solo_si_tiene_canal_web(env):
    client, ids, TestSession = env
    with TestSession() as s:
        sin_web = Promocion(
            empresa_id=uuid.UUID(ids["empresa_id"]), nombre="Solo PDV", tipo="monto_minimo",
            canales=["pdv"], condicion={}, beneficio={},
        )
        con_web = Promocion(
            empresa_id=uuid.UUID(ids["empresa_id"]), nombre="Web 2x1", tipo="monto_minimo",
            canales=["web", "delivery"], condicion={}, beneficio={},
        )
        s.add_all([sin_web, con_web])
        s.commit()

    r = client.get(f"{PUBLICO}/promociones")
    assert r.status_code == 200
    nombres = [p["nombre"] for p in r.json()]
    assert nombres == ["Web 2x1"]


def test_convocatoria_solo_si_publicada_y_sin_remuneracion(env):
    client, ids, TestSession = env
    with TestSession() as s:
        borrador = Convocatoria(
            empresa_id=uuid.UUID(ids["empresa_id"]), puesto="Cajero", motivo="refuerzo",
            vacantes=1, estado="borrador",
        )
        publicada = Convocatoria(
            empresa_id=uuid.UUID(ids["empresa_id"]), puesto="Cocinero", motivo="refuerzo",
            vacantes=2, estado="publicada", token_publico="tok-" + uuid.uuid4().hex,
            remuneracion_min=Decimal("1000"), remuneracion_max=Decimal("1200"),
        )
        s.add_all([borrador, publicada])
        s.commit()

    r = client.get(f"{PUBLICO}/convocatorias")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["puesto"] == "Cocinero"
    assert body[0]["url_postular"].endswith("/postular/" + body[0]["token"])
    assert "remuneracion_min" not in r.text
    assert "remuneracion_max" not in r.text


def test_el_rate_limit_corta(env, monkeypatch):
    from src.core import rate_limit

    client, ids, _ = env
    llamadas = {"n": 0}

    def _contar(nombre, sujeto, intentos, ventana):
        if nombre != "storefront_publico":
            return
        llamadas["n"] += 1
        if llamadas["n"] > intentos:
            from fastapi import HTTPException, status

            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas solicitudes")

    monkeypatch.setattr(rate_limit, "consumir", _contar)
    codigos = [client.get(f"{PUBLICO}/contenido").status_code for _ in range(125)]
    assert 429 in codigos


def test_un_producto_fuera_del_canal_no_sale_en_la_carta(env):
    """`canales` saca de la web lo que solo existe en el PDV (cajas, propinas)."""
    client, ids, _ = env
    headers = _token(client)
    _crear_lista_y_precio(client, headers, ids)
    url = f"/api/v1/sales/productos/{ids['producto_id']}"

    def en_carta():
        return len(client.get(f"{PUBLICO}/carta").json()["productos"])

    assert en_carta() == 1  # sin `canales` = todos
    r = client.patch(url, headers=headers, json={"canales": ["pdv"]})
    assert r.status_code == 200 and r.json()["canales"] == ["pdv"]
    assert en_carta() == 0  # el canal del sitio en este test es `delivery`
    r = client.patch(url, headers=headers, json={"canales": ["pdv", "delivery"]})
    assert r.status_code == 200
    assert en_carta() == 1
    r = client.patch(url, headers=headers, json={"canales": []})  # [] = todos otra vez
    assert r.json()["canales"] is None
    assert en_carta() == 1


def test_canal_inexistente_es_rechazado(env):
    client, ids, _ = env
    r = client.patch(
        f"/api/v1/sales/productos/{ids['producto_id']}",
        headers=_token(client),
        json={"canales": ["kiosko"]},
    )
    assert r.status_code == 422  # kiosko no es canal de venta: es `pdv`


def test_tiempo_de_preparacion_se_edita_y_se_limpia(env):
    client, ids, _ = env
    headers = _token(client)
    url = f"/api/v1/sales/productos/{ids['producto_id']}"
    r = client.patch(url, headers=headers, json={"tiempo_preparacion_min": 0})
    assert r.json()["tiempo_preparacion_min"] == 0  # 0 = sale al instante, no "vacío"
    r = client.patch(url, headers=headers, json={"quitar_tiempo_preparacion": True})
    assert r.json()["tiempo_preparacion_min"] is None
    r = client.patch(url, headers=headers, json={"tiempo_preparacion_min": 500})
    assert r.status_code == 422
