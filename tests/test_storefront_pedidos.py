"""Checkout del sitio de marca (`/storefront/publico/pedidos*`,
ADR-105): invitado y logueado, asignación de local, ETA, efectivo e
Izipay, idempotencia y el token de consulta para un invitado sin cuenta.
"""

import json
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
    VentaItem,
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
        # El efectivo exige cuenta (RN-WEB-013): los pedidos de estas pruebas
        # salen con una; los del invitado piden `headers={}` a propósito.
        r = c.post(
            "/api/v1/storefront/cuentas/registro",
            json={
                "email": "cliente@example.com", "password": "clave-larga-123",
                "nombres": "Carlos", "apellidos": "Pérez", "tipo_documento": "dni",
                "numero_documento": "45678912", "telefono": "987654321",
                "fecha_nacimiento": "1995-05-20", "direccion": "Jr. Los Pinos 123",
            },
        )
        assert r.status_code == 201, r.text
        ids["auth"] = {"Authorization": "Bearer " + r.json()["access_token"]}
        yield c, ids, TestSession


def _auth(ids):
    return ids["auth"]


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


def test_confirmar_pedido_recojo_efectivo_con_cuenta(env):
    client, ids, TestSession = env
    r = client.post(PEDIDOS, headers=_auth(ids), json=_body_takeout(ids, "recojo-001"))
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
        assert venta.estado == "orden"  # efectivo: se cobra al recoger, no ahora
        assert venta.cliente_id is not None  # el de la cuenta
        assert venta.referencia_atencion == "Carlos Pérez"


def test_pedido_de_invitado_reutiliza_el_cliente_del_mismo_telefono(env):
    from src.modules.sales.application.queries_publicas import contacto_de_cliente

    client, ids, TestSession = env
    for clave in ("invitado-001", "invitado-002"):
        pedido = _pedido_izipay(client, ids, clave)
        assert _webhook(client, pedido["pago_id_externo"]).status_code == 200

    with TestSession() as s:
        ventas = s.scalars(select(Venta).where(Venta.canal == "web")).all()
        assert len(ventas) == 2
        assert ventas[0].cliente_id == ventas[1].cliente_id
        contacto = contacto_de_cliente(s, ventas[0].cliente_id)
        assert contacto["nombre"] == "Carlos Pérez"
        assert contacto["telefono"] == "987654321"


def test_carga_de_cocina_ignora_ordenes_viejas_sin_cerrar(env):
    from datetime import UTC, datetime, timedelta

    from src.modules.sales.application.queries_publicas import carga_activa_por_sucursal

    client, ids, TestSession = env
    for n in range(2):
        r = client.post(
            PEDIDOS, headers=_auth(ids), json=_body_takeout(ids, f"carga-cocina-{n}")
        )
        assert r.status_code == 201

    ch1 = uuid.UUID(ids["ch1_id"])
    with TestSession() as s:
        assert carga_activa_por_sucursal(s, [ch1]) == {ch1: 2}
        # Una comanda de hace 5 horas que nadie cerró ya no es cola de cocina.
        vieja = s.scalars(select(Venta).where(Venta.canal == "web")).first()
        vieja.created_at = datetime.now(UTC) - timedelta(hours=5)
        s.commit()
        assert carga_activa_por_sucursal(s, [ch1]) == {ch1: 1}


def test_confirmar_pedido_delivery_asigna_la_sucursal_mas_cercana(env):
    client, ids, _ = env
    r = client.post(
        PEDIDOS, headers=_auth(ids), json=_body_delivery(ids, "deliv-001", CH2_LAT, CH2_LNG)
    )
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

    r = client.post(
        PEDIDOS, headers=_auth(ids), json=_body_delivery(ids, "deliv-002", CH1_LAT, CH1_LNG)
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # CH1 está saturada: se prefiere CH2 aunque CH1 sea la más cercana.
    assert body["sucursal_id"] == ids["ch2_id"]


def test_confirmar_pedido_fuera_de_cobertura(env, monkeypatch):
    client, ids, _ = env
    from src.config.settings import settings

    monkeypatch.setattr(settings, "delivery_distancia_maxima_km", Decimal("0.001"))
    lejos_lat, lejos_lng = Decimal("-6.700000"), Decimal("-76.600000")
    r = client.post(
        PEDIDOS, headers=_auth(ids), json=_body_delivery(ids, "deliv-003", lejos_lat, lejos_lng)
    )
    assert r.status_code == 409, r.text


def test_idempotencia_del_pedido(env):
    client, ids, _ = env
    r1 = client.post(PEDIDOS, headers=_auth(ids), json=_body_takeout(ids, "idem-001"))
    r2 = client.post(PEDIDOS, headers=_auth(ids), json=_body_takeout(ids, "idem-001"))
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


WEBHOOK = "/api/v1/storefront/webhooks/izipay"


def _webhook(client, id_externo, resultado="aprobado"):
    return client.post(
        WEBHOOK, json={"id_externo": id_externo}, headers={"X-Izipay-Fake": resultado}
    )


def _pedido_izipay(client, ids, clave):
    """Un invitado paga por adelantado: queda pendiente hasta el webhook."""
    r = client.post(PEDIDOS, json=_body_takeout(ids, clave, medio_pago="izipay"))
    assert r.status_code == 201, r.text
    return r.json()


def test_invitado_no_puede_pagar_en_efectivo(env):
    client, ids, _ = env
    r = client.post(PEDIDOS, json=_body_takeout(ids, "sin-cuenta-001"))
    assert r.status_code == 409, r.text
    assert "cuenta" in r.json()["detail"]


def test_pago_izipay_deja_el_pedido_pendiente_hasta_el_webhook(env):
    client, ids, TestSession = env
    pedido = _pedido_izipay(client, ids, "izipay-001")
    assert pedido["estado"] == "pendiente"
    assert pedido["pago_estado"] == "pendiente"
    assert pedido["pago_simulado"] is True
    assert pedido["pago_id_externo"].startswith("fake-")

    with TestSession() as s:
        # Sin pagar no hay venta: nada llega a cocina.
        assert s.scalar(select(Venta).where(Venta.canal == "web")) is None

    r = _webhook(client, pedido["pago_id_externo"])
    assert r.status_code == 200, r.text

    visto = client.get(
        f"{PEDIDOS}/{pedido['id']}", params={"token": pedido["token_acceso"]}
    ).json()
    assert visto["estado"] == "confirmado"
    assert visto["pago_estado"] == "aprobado"
    assert visto["numero_orden"] is not None

    with TestSession() as s:
        venta = s.scalar(select(Venta).where(Venta.numero_orden == visto["numero_orden"]))
        assert venta is not None
        pago = s.scalar(select(Pago).where(Pago.venta_id == venta.id))
        assert pago is not None
        assert pago.estado == "confirmado"
        medio = s.scalar(select(MedioPago).where(MedioPago.id == pago.medio_pago_id))
        assert medio.nombre.lower() == "izipay"


def test_el_webhook_es_idempotente(env):
    client, ids, TestSession = env
    pedido = _pedido_izipay(client, ids, "izipay-002")
    for _ in range(3):  # la pasarela reintenta hasta que se le contesta
        assert _webhook(client, pedido["pago_id_externo"]).status_code == 200

    with TestSession() as s:
        assert len(s.scalars(select(Venta).where(Venta.canal == "web")).all()) == 1
        assert len(s.scalars(select(Pago)).all()) == 1


def test_pago_rechazado_cierra_el_pedido_sin_venta(env):
    client, ids, TestSession = env
    pedido = _pedido_izipay(client, ids, "izipay-003")
    assert _webhook(client, pedido["pago_id_externo"], "rechazado").status_code == 200

    visto = client.get(
        f"{PEDIDOS}/{pedido['id']}", params={"token": pedido["token_acceso"]}
    ).json()
    assert visto["estado"] == "fallido"
    assert visto["pago_estado"] == "rechazado"
    with TestSession() as s:
        assert s.scalar(select(Venta).where(Venta.canal == "web")) is None
    # Un aviso tardío de "aprobado" no resucita un pedido ya rechazado.
    assert _webhook(client, pedido["pago_id_externo"]).status_code == 200
    with TestSession() as s:
        assert s.scalar(select(Venta).where(Venta.canal == "web")) is None


def test_webhook_con_pago_desconocido_o_firma_invalida(env):
    client, ids, _ = env
    assert _webhook(client, "fake-que-no-existe").status_code == 404
    r = client.post(WEBHOOK, json={"id_externo": "x"}, headers={"X-Izipay-Fake": "quizas"})
    assert r.status_code == 400
    assert client.post(WEBHOOK, content=b"no es json").status_code == 400


def test_en_produccion_sin_credenciales_izipay_no_se_puede_usar(env, monkeypatch):
    from src.config.settings import settings

    client, ids, _ = env
    pedido = _pedido_izipay(client, ids, "izipay-004")
    monkeypatch.setattr(settings, "environment", "production")
    # El webhook de mentira no existe en producción: nadie aprueba sin pagar.
    assert _webhook(client, pedido["pago_id_externo"]).status_code == 400
    # Y el checkout ya no ofrece cobrar con una pasarela que no cobra.
    r = client.post(PEDIDOS, json=_body_takeout(ids, "izipay-005", medio_pago="izipay"))
    assert r.status_code == 409


def test_token_de_invitado_permite_consultar_su_pedido(env):
    client, ids, _ = env
    r = client.post(PEDIDOS, json=_body_takeout(ids, "token-001", medio_pago="izipay"))
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


def test_cotizar_usa_el_tiempo_de_preparacion_de_lo_que_se_pide(env):
    client, ids, TestSession = env
    with TestSession() as s:
        pizza = s.get(ProductoComercial, uuid.UUID(ids["producto_id"]))
        pizza.tiempo_preparacion_min = 25
        agua = ProductoComercial(
            id_interno="P0000098", marca_id=pizza.marca_id, nombre="Agua",
            tiempo_preparacion_min=0,
        )
        s.add(agua)
        s.commit()
        agua_id = str(agua.id)

    def cotizar(items):
        r = client.post(
            COTIZAR,
            json={"modalidad": "takeout", "sucursal_id": ids["ch1_id"], "items": items},
        )
        assert r.status_code == 200, r.text
        return (r.json()["eta_min"], r.json()["eta_max"])

    pizza = {"producto_comercial_id": ids["producto_id"], "cantidad": 2}
    agua = {"producto_comercial_id": agua_id, "cantidad": 1}
    assert cotizar([agua]) == (5, 10)  # la botella de agua ya no espera 70 min
    assert cotizar([pizza]) == (25, 40)
    assert cotizar([pizza, agua]) == (25, 40)  # manda lo que más tarda
    assert cotizar([]) == (30, 45)  # sin carrito: la base estándar


def test_variante_sin_tiempo_propio_hereda_el_de_su_padre(env):
    from src.modules.sales.application.queries_publicas import tiempos_preparacion

    _, ids, TestSession = env
    with TestSession() as s:
        padre = s.get(ProductoComercial, uuid.UUID(ids["producto_id"]))
        padre.tiempo_preparacion_min = 25
        hija = ProductoComercial(
            id_interno="P0000097", marca_id=padre.marca_id, nombre="Familiar",
            producto_padre_id=padre.id,
        )
        propia = ProductoComercial(
            id_interno="P0000096", marca_id=padre.marca_id, nombre="Personal",
            producto_padre_id=padre.id, tiempo_preparacion_min=15,
        )
        s.add_all([hija, propia])
        s.commit()
        tiempos = tiempos_preparacion(s, [hija.id, propia.id, padre.id])
        assert tiempos == {hija.id: 25, propia.id: 15, padre.id: 25}


# --- extras y Mitad x Mitad (RN-WEB-017) --------------------------------------


def _pizza_mitad_y_mitad(TestSession, ids):
    """Una pizza de 40 con extras (queso hasta 2, tocino, champiñones) y dos
    mitades (Hawaiana suma 3 en la primera). Hawaiana con Hawaiana y Peperoni con
    Peperoni están excluidas: no es una mitad y mitad, es una entera."""
    from src.modules.sales.application import atributos, catalogo
    from src.modules.sales.infrastructure.models import ListaPrecio

    with TestSession() as s:
        base = s.get(ProductoComercial, uuid.UUID(ids["producto_id"]))
        empresa = s.scalar(select(Empresa))
        lista = s.scalar(select(ListaPrecio).where(ListaPrecio.nombre == "General"))

        def producto(codigo, nombre, monto, **campos):
            p = ProductoComercial(
                id_interno=codigo, marca_id=base.marca_id, nombre=nombre,
                receta_id=base.receta_id, **campos,
            )
            s.add(p)
            s.flush()
            precios.fijar_precio(
                s, lista_precio_id=lista.id, producto_comercial_id=p.id,
                monto=Decimal(monto),
            )
            return p

        pizza = producto("P0000090", "Pizza Mitad", "40.00")
        queso = producto("P0000091", "Extra Queso", "6.00", es_extra=True)
        tocino = producto("P0000092", "Extra Tocino", "8.00", es_extra=True)
        champi = producto("P0000093", "Extra Champinon", "5.00", es_extra=True)
        ajeno = producto("P0000094", "Extra Ajeno", "4.00", es_extra=True)  # sin vincular
        catalogo.vincular_extra(s, producto_id=pizza.id, extra_id=queso.id, maximo=2)
        catalogo.vincular_extra(s, producto_id=pizza.id, extra_id=tocino.id)
        catalogo.vincular_extra(s, producto_id=pizza.id, extra_id=champi.id)

        valores = {}
        for nombre_atributo in ("Mitad 1", "Mitad 2"):
            atributo = atributos.crear_atributo(
                s, empresa_id=empresa.id, nombre=nombre_atributo
            )
            for sabor in ("Hawaiana", "Peperoni"):
                atributos.agregar_valor(s, atributo.id, nombre=sabor)
            linea = atributos.ofrecer_atributo(
                s, producto_id=pizza.id, atributo_id=atributo.id
            )
            nombres = {v.id: v.nombre for v in atributos.valores_de(s, atributo.id)}
            for ptav in atributos.ptav_de_linea(s, linea.id):
                valores[(nombre_atributo, nombres[ptav.atributo_valor_id])] = str(ptav.id)
        atributos.fijar_precio_extra(
            s, uuid.UUID(valores[("Mitad 1", "Hawaiana")]), precio_extra=Decimal("3.00")
        )
        for sabor in ("Hawaiana", "Peperoni"):
            atributos.excluir(
                s,
                valor_id=uuid.UUID(valores[("Mitad 1", sabor)]),
                excluye_id=uuid.UUID(valores[("Mitad 2", sabor)]),
            )
        s.commit()
        return {
            "pizza": str(pizza.id), "queso": str(queso.id), "tocino": str(tocino.id),
            "champi": str(champi.id), "ajeno": str(ajeno.id),
            "h1": valores[("Mitad 1", "Hawaiana")], "p1": valores[("Mitad 1", "Peperoni")],
            "h2": valores[("Mitad 2", "Hawaiana")], "p2": valores[("Mitad 2", "Peperoni")],
        }


def _linea(o, cantidad, valores, extras=()):
    return {
        "producto_comercial_id": o["pizza"],
        "cantidad": cantidad,
        "valores_variante_ids": valores,
        "extras": [{"producto_comercial_id": e, "cantidad": c} for e, c in extras],
    }


def _pedir(client, ids, linea, clave, **kw):
    body = {**_body_takeout(ids, clave, **kw), "items": [linea]}
    return client.post(PEDIDOS, headers=_auth(ids), json=body)


def test_el_detalle_publico_trae_las_opciones_y_la_carta_no_las_repite(env):
    client, ids, TestSession = env
    o = _pizza_mitad_y_mitad(TestSession, ids)

    det = client.get(f"/api/v1/storefront/publico/productos/{o['pizza']}")
    assert det.status_code == 200, det.text
    det = det.json()
    assert {a["nombre"] for a in det["atributos"]} == {"Mitad 1", "Mitad 2"}
    assert {e["nombre"] for e in det["extras"]} == {
        "Extra Queso", "Extra Tocino", "Extra Champinon",
    }
    hawaiana = next(
        v for a in det["atributos"] if a["nombre"] == "Mitad 1"
        for v in a["valores"] if v["nombre"] == "Hawaiana"
    )
    assert Decimal(hawaiana["precio_extra"]) == Decimal("3.00")
    assert len(det["exclusiones"]) == 2
    assert "id_interno" not in json.dumps(det) and "empresa_id" not in json.dumps(det)

    carta = client.get("/api/v1/storefront/publico/carta").json()
    ficha = next(p for p in carta["productos"] if p["id"] == o["pizza"])
    assert ficha["extras"] == [] and ficha["atributos"] == []  # liviana


def test_mitad_y_mitad_con_extras_cobra_lo_mismo_que_el_pdv(env):
    client, ids, TestSession = env
    o = _pizza_mitad_y_mitad(TestSession, ids)
    linea = _linea(o, 2, [o["h1"], o["p2"]], [(o["queso"], 2), (o["tocino"], 1)])
    r = _pedir(client, ids, linea, "mitad-001")
    assert r.status_code == 201, r.text
    body = r.json()
    # (40 + 3 de la Hawaiana + 2x6 + 8) x 2 pizzas
    assert Decimal(body["total_estimado"]) == Decimal("126.00")
    assert body["estado"] == "confirmado"
    assert body["items"][0]["valores"] == ["Hawaiana", "Peperoni"]
    assert {(e["nombre"], e["cantidad"]) for e in body["items"][0]["extras"]} == {
        ("Extra Queso", 2), ("Extra Tocino", 1),
    }

    with TestSession() as s:
        venta = s.scalar(select(Venta).where(Venta.numero_orden == body["numero_orden"]))
        assert venta.total == Decimal("126.00")  # el mismo número que mostró la web
        lineas = s.scalars(select(VentaItem).where(VentaItem.venta_id == venta.id)).all()
        padre = next(i for i in lineas if i.padre_venta_item_id is None)
        assert padre.precio_unitario == Decimal("43.00")  # con el recargo de la Hawaiana
        assert sorted(padre.valores_variante_ids) == sorted([o["h1"], o["p2"]])
        hijos = {
            str(i.producto_comercial_id): i for i in lineas
            if i.padre_venta_item_id == padre.id
        }
        # La cantidad del extra es por pizza: 2 pizzas x 2 quesos = 4 porciones.
        assert hijos[o["queso"]].cantidad == 4 and hijos[o["queso"]].precio_unitario == 6
        assert hijos[o["tocino"]].cantidad == 2


@pytest.mark.parametrize(
    ("armar", "mensaje"),
    [
        (lambda o: ([o["h1"]], []), "falta elegir Mitad 2"),
        (lambda o: ([o["h1"], o["h2"]], []), "esa combinación no se puede pedir"),
        (lambda o: ([o["h1"], o["p2"]], [("tocino", 2), ("queso", 2)]), "máximo 3 extras"),
        (lambda o: ([o["h1"], o["p2"]], [("queso", 3)]), "admite hasta 2"),
        (lambda o: ([o["h1"], o["p2"]], [("ajeno", 1)]), "ya no se ofrece"),
    ],
)
def test_una_linea_que_sales_rechazaria_se_rechaza_antes_de_crear_nada(env, armar, mensaje):
    client, ids, TestSession = env
    o = _pizza_mitad_y_mitad(TestSession, ids)
    valores, extras = armar(o)
    linea = _linea(o, 1, valores, [(o[nombre], c) for nombre, c in extras])
    r = _pedir(client, ids, linea, "rechazo-001")
    assert r.status_code == 409, r.text
    assert mensaje in r.json()["detail"]
    with TestSession() as s:
        assert s.scalar(select(Venta).where(Venta.canal == "web")) is None


def test_izipay_con_opciones_cobra_el_total_y_arma_la_venta_al_aprobarse(env):
    """Con Izipay la venta nace después, desde lo guardado: las opciones tienen
    que sobrevivir ese viaje (pedido guardado → evento → `crear_venta`)."""
    client, ids, TestSession = env
    o = _pizza_mitad_y_mitad(TestSession, ids)
    linea = _linea(o, 1, [o["p1"], o["h2"]], [(o["champi"], 1)])
    body = {**_body_takeout(ids, "mitad-izipay", medio_pago="izipay"), "items": [linea]}
    r = client.post(PEDIDOS, json=body)  # invitado
    assert r.status_code == 201, r.text
    pedido = r.json()
    assert pedido["estado"] == "pendiente"
    assert Decimal(pedido["total_estimado"]) == Decimal("45.00")  # 40 + 5, sin recargo

    assert _webhook(client, pedido["pago_id_externo"]).status_code == 200
    visto = client.get(
        f"{PEDIDOS}/{pedido['id']}", params={"token": pedido["token_acceso"]}
    ).json()
    assert visto["estado"] == "confirmado"

    with TestSession() as s:
        venta = s.scalar(select(Venta).where(Venta.numero_orden == visto["numero_orden"]))
        pago = s.scalar(select(Pago).where(Pago.venta_id == venta.id))
        assert venta.total == Decimal("45.00") == pago.monto
        lineas = s.scalars(select(VentaItem).where(VentaItem.venta_id == venta.id)).all()
        padre = next(i for i in lineas if i.padre_venta_item_id is None)
        assert sorted(padre.valores_variante_ids) == sorted([o["p1"], o["h2"]])
        assert any(str(i.producto_comercial_id) == o["champi"] for i in lineas)
