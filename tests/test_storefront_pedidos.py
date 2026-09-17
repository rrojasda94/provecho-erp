"""Checkout del sitio de marca (`/storefront/publico/pedidos*`,
ADR-105): invitado y logueado, asignación de local, ETA, efectivo e
Izipay, idempotencia y el token de consulta para un invitado sin cuenta.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.sales.application import listeners as sales_listeners
from src.modules.sales.application import precios
from src.modules.sales.infrastructure.models import (
    MedioPago,
    Pago,
    ProductoComercial,
    PuntoVenta,
    Venta,
)
from src.modules.storefront.application import listeners as storefront_listeners
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Sucursal,
    Usuario,
)

PEDIDOS = "/api/v1/storefront/publico/pedidos"
COTIZAR = f"{PEDIDOS}/cotizar"

CH1_LAT, CH1_LNG = Decimal("-6.499000"), Decimal("-76.359000")
CH2_LAT, CH2_LNG = Decimal("-6.510000"), Decimal("-76.370000")


def _serie(prefijo: str, n: int) -> str:
    return f"{prefijo}{n:03d}"


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(sales_listeners, "session_factory", TestSession)
    monkeypatch.setattr(storefront_listeners, "session_factory", TestSession)
    # `crear_venta` descuenta stock vía `sales.venta_confirmada`: sin esto el
    # listener de `inventory` (ya en `MODULOS_CON_SESSION_FACTORY`) queda
    # apuntando a `_sin_base_real` y el descuento nunca toca esta base.
    monkeypatch.setattr(inventory_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
        ch1 = s.scalar(select(Sucursal).where(Sucursal.nombre == "CH1"))
        ch2 = s.scalar(select(Sucursal).where(Sucursal.nombre == "CH2"))
        ch1.ubicacion_lat, ch1.ubicacion_lng = CH1_LAT, CH1_LNG
        ch2.ubicacion_lat, ch2.ubicacion_lng = CH2_LAT, CH2_LNG

        pv1 = PuntoVenta(
            sucursal_id=ch1.id, canal="web", serie_boleta=_serie("B", 1),
            serie_factura=_serie("F", 1), modalidades_habilitadas=["delivery", "takeout"],
            politica_pago="adelantado",
        )
        pv2 = PuntoVenta(
            sucursal_id=ch2.id, canal="web", serie_boleta=_serie("B", 2),
            serie_factura=_serie("F", 2), modalidades_habilitadas=["delivery", "takeout"],
            politica_pago="adelantado",
        )
        almacen1 = Almacen(
            empresa_id=empresa.id, sucursal_id=ch1.id, nombre="WH-CH1", tipo="sucursal"
        )
        almacen2 = Almacen(
            empresa_id=empresa.id, sucursal_id=ch2.id, nombre="WH-CH2", tipo="sucursal"
        )
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([pv1, pv2, almacen1, almacen2, udm_cat])
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
            empresa_id=empresa.id, nombre="Pizza base", rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=udm.id,
        )
        s.add_all([sku, receta])
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal("0.25")))
        s.add(Stock(almacen_id=almacen1.id, sku_id=sku.id, cantidad=Decimal(100)))
        s.add(Stock(almacen_id=almacen2.id, sku_id=sku.id, cantidad=Decimal(100)))

        producto = ProductoComercial(
            id_interno="P0000099", marca_id=marca.id, nombre="Pizza Familiar",
            receta_id=receta.id,
        )
        s.add(producto)
        s.flush()
        lista = precios.crear_lista(
            s, marca_id=marca.id, nombre="General", vigente_desde=date(2020, 1, 1)
        )
        precios.fijar_precio(
            s, lista_precio_id=lista.id, producto_comercial_id=producto.id,
            monto=Decimal("35.00"),
        )
        admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))

        ids.update(
            marca_id=str(marca.id), producto_id=str(producto.id),
            ch1_id=str(ch1.id), ch2_id=str(ch2.id), pv1_id=str(pv1.id),
            pv2_id=str(pv2.id), admin_id=str(admin.id),
        )
        s.commit()

    from src.config.settings import settings

    monkeypatch.setattr(settings, "storefront_marca_id", ids["marca_id"])
    monkeypatch.setattr(settings, "delivery_distancia_maxima_km", Decimal("0"))
    monkeypatch.setattr(settings, "storefront_saturacion_pedidos", 4)

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


def _items(ids, cantidad=2):
    return [{"producto_comercial_id": ids["producto_id"], "cantidad": cantidad}]


def _body_takeout(ids, idem: str, medio_pago="efectivo"):
    return {
        "modalidad": "takeout",
        "sucursal_id": ids["ch1_id"],
        "items": _items(ids),
        "nombre_contacto": "Carlos Pérez",
        "telefono_contacto": "987654321",
        "medio_pago": medio_pago,
        "numero_documento": "12345678",
        "idempotency_key": idem,
    }


def _body_delivery(ids, idem: str, lat: Decimal, lng: Decimal, medio_pago="efectivo"):
    return {
        "modalidad": "delivery",
        "items": _items(ids),
        "nombre_contacto": "Carlos Pérez",
        "telefono_contacto": "987654321",
        "medio_pago": medio_pago,
        "direccion_entrega": "Jr. Falso 123",
        "ubicacion_lat": str(lat),
        "ubicacion_lng": str(lng),
        "idempotency_key": idem,
    }


def test_confirmar_pedido_recojo_efectivo_invitado(env):
    client, ids, TestSession = env
    r = client.post(PEDIDOS, json=_body_takeout(ids, "recojo-001"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "confirmado"
    assert body["numero_orden"] is not None
    assert body["sucursal_id"] == ids["ch1_id"]
    assert Decimal(body["total_estimado"]) == Decimal("70.00")
    assert body["token_acceso"]

    with TestSession() as s:
        venta = s.scalar(select(Venta).where(Venta.numero_orden == body["numero_orden"]))
        assert venta is not None
        assert venta.canal == "web"
        assert venta.modalidad == "takeout"
        assert venta.cliente_id is None
        assert venta.estado == "orden"  # efectivo: se cobra al recoger, no ahora


def test_confirmar_pedido_delivery_asigna_la_sucursal_mas_cercana(env):
    client, ids, _ = env
    r = client.post(PEDIDOS, json=_body_delivery(ids, "deliv-001", CH2_LAT, CH2_LNG))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "confirmado"
    assert body["sucursal_id"] == ids["ch2_id"]
    assert body["costo_delivery_estimado"] is not None
    assert body["eta_min"] and body["eta_max"] and body["eta_max"] > body["eta_min"]


def test_confirmar_pedido_delivery_evita_sucursal_saturada(env):
    client, ids, TestSession = env
    # Satura CH1 (la más cercana al destino elegido) con `storefront_
    # saturacion_pedidos` ventas `orden` de más.
    with TestSession() as s:
        admin_id = uuid.UUID(ids["admin_id"])
        for i in range(5):
            s.add(
                Venta(
                    sucursal_id=uuid.UUID(ids["ch1_id"]),
                    punto_venta_id=uuid.UUID(ids["pv1_id"]),
                    canal="pdv",
                    modalidad="mesa",
                    usuario_id=admin_id,
                    estado="orden",
                    numero_orden=1000 + i,
                    idempotency_key=f"carga-{i}",
                )
            )
        s.commit()

    r = client.post(PEDIDOS, json=_body_delivery(ids, "deliv-002", CH1_LAT, CH1_LNG))
    assert r.status_code == 201, r.text
    body = r.json()
    # CH1 está saturada: se prefiere CH2 aunque CH1 sea la más cercana.
    assert body["sucursal_id"] == ids["ch2_id"]


def test_confirmar_pedido_fuera_de_cobertura(env, monkeypatch):
    client, ids, _ = env
    from src.config.settings import settings

    monkeypatch.setattr(settings, "delivery_distancia_maxima_km", Decimal("0.001"))
    lejos_lat, lejos_lng = Decimal("-6.700000"), Decimal("-76.600000")
    r = client.post(PEDIDOS, json=_body_delivery(ids, "deliv-003", lejos_lat, lejos_lng))
    assert r.status_code == 409, r.text


def test_idempotencia_del_pedido(env):
    client, ids, _ = env
    r1 = client.post(PEDIDOS, json=_body_takeout(ids, "idem-001"))
    r2 = client.post(PEDIDOS, json=_body_takeout(ids, "idem-001"))
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_pago_izipay_registra_pago_sin_exigir_caja(env):
    client, ids, TestSession = env
    r = client.post(PEDIDOS, json=_body_takeout(ids, "izipay-001", medio_pago="izipay"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "confirmado"

    with TestSession() as s:
        venta = s.scalar(select(Venta).where(Venta.numero_orden == body["numero_orden"]))
        assert venta is not None
        pago = s.scalar(select(Pago).where(Pago.venta_id == venta.id))
        assert pago is not None
        assert pago.estado == "confirmado"
        medio = s.scalar(select(MedioPago).where(MedioPago.id == pago.medio_pago_id))
        assert medio.nombre.lower() == "izipay"


def test_token_de_invitado_permite_consultar_su_pedido(env):
    client, ids, _ = env
    r = client.post(PEDIDOS, json=_body_takeout(ids, "token-001"))
    pedido_id = r.json()["id"]
    token = r.json()["token_acceso"]

    ok = client.get(f"{PEDIDOS}/{pedido_id}", params={"token": token})
    assert ok.status_code == 200
    assert ok.json()["token_acceso"] is None  # no se re-expone

    mal = client.get(f"{PEDIDOS}/{pedido_id}", params={"token": "lo-que-sea"})
    assert mal.status_code == 404


def test_cotizar_delivery_devuelve_sucursal_y_eta(env):
    client, ids, _ = env
    r = client.post(
        COTIZAR,
        json={
            "modalidad": "delivery",
            "ubicacion_lat": str(CH1_LAT),
            "ubicacion_lng": str(CH1_LNG),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sucursal_id"] == ids["ch1_id"]
    assert body["eta_min"] > 0
