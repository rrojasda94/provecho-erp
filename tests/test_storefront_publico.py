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
