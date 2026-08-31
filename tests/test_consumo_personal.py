"""Consumo de personal (RN-COM-025): la comida del staff.

Se prepara y se despacha como cualquier pedido, pero vale cero, no se cobra,
no emite comprobante y su costo termina en gasto de alimentación de personal.
La cadena completa —venta → inventario → contabilidad— se ejercita entera:
lo que hace valiosa a esta función es justamente que el costo llegue al
final, y un test por capa no lo demuestra.
"""

import uuid
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
from src.modules.accounting.application import listeners as accounting_listeners
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    MovimientoInventario,
    Receta,
    RecetaItem,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    MedioPago,
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa, Marca, Sucursal
from src.shared import fechas
from tests.conftest import abrir_caja_directa

#: Costo del insumo y cuánto lleva un plato: el consumo vale 2 × 3.00 = 6.00.
COSTO_INSUMO = Decimal("3.00")
INSUMO_POR_PLATO = Decimal(2)
COSTO_ESPERADO = COSTO_INSUMO * INSUMO_POR_PLATO


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(inventory_listeners, "session_factory", TestSession)
    monkeypatch.setattr(accounting_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        marca = s.scalar(select(Marca))
        sucursal = s.scalar(select(Sucursal))

        # El listener de inventario descuenta del almacén de la sucursal: sin
        # él la venta pasa igual pero no mueve stock (queda una incidencia).
        almacen = Almacen(
            empresa_id=empresa.id,
            sucursal_id=sucursal.id,
            nombre="Almacén Local 1",
            tipo="sucursal",
        )
        cat_udm = CategoriaUdm(nombre="Unidades")
        s.add_all([almacen, cat_udm])
        s.flush()
        udm = UnidadMedida(
            categoria_udm_id=cat_udm.id, nombre="Unidad", ratio=Decimal(1)
        )
        categoria = Categoria(empresa_id=empresa.id, nombre="Insumos")
        s.add_all([udm, categoria])
        s.flush()
        articulo = Articulo(
            empresa_id=empresa.id,
            id_interno="I001",
            nombre="Masa",
            categoria_id=categoria.id,
            unidad_medida_id=udm.id,
            tipo="insumo",
            costo_promedio=COSTO_INSUMO,
        )
        s.add(articulo)
        s.flush()
        sku = Sku(articulo_id=articulo.id, codigo="MASA-001")
        receta = Receta(
            empresa_id=empresa.id,
            nombre="Pizza",
            rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=udm.id,
        )
        s.add_all([sku, receta])
        s.flush()
        s.add_all(
            [
                RecetaItem(
                    receta_id=receta.id,
                    articulo_id=articulo.id,
                    cantidad=INSUMO_POR_PLATO,
                ),
                Stock(almacen_id=almacen.id, sku_id=sku.id, cantidad=Decimal(100)),
            ]
        )
        producto = ProductoComercial(
            id_interno="P001",
            marca_id=marca.id,
            nombre="Pizza Pepperoni",
            receta_id=receta.id,
        )
        punto_venta = PuntoVenta(
            sucursal_id=sucursal.id,
            canal="trabajador",
            serie_boleta="B001",
            serie_factura="F001",
            politica_pago="al_finalizar",
        )
        medio = MedioPago(
            empresa_id=empresa.id,
            nombre="Efectivo",
            direccion="cobro",
            tipo="efectivo",
        )
        s.add_all([producto, punto_venta, medio])
        s.flush()
        # El cobro exige turno abierto (RN-MDP-002): este archivo no prueba la
        # caja, pero sí que un consumo de personal se rechace **por ser
        # consumo**, no por falta de turno.
        from src.modules.users.infrastructure.models import Usuario

        admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
        abrir_caja_directa(
            session=s, punto_venta_id=punto_venta.id, cajero_id=admin.id
        )
        ids.update(
            empresa_id=str(empresa.id),
            sucursal_id=str(sucursal.id),
            almacen_id=str(almacen.id),
            sku_id=str(sku.id),
            producto_id=str(producto.id),
            punto_venta_id=str(punto_venta.id),
            medio_id=str(medio.id),
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
        yield c, ids, TestSession


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _autorizacion(
    client,
    permiso="sales.registrar_consumo_personal",
    username="admin",
    pin="123456",
):
    r = client.post(
        "/api/v1/auth/autorizar",
        json={"username": username, "pin": pin, "permiso": permiso},
    )
    assert r.status_code == 200, r.text
    return r.json()["autorizacion"]


def _crear_consumo(client, h, ids, *, motivo="feriado", autorizacion=..., **extra):
    cuerpo = {
        "sucursal_id": ids["sucursal_id"],
        "punto_venta_id": ids["punto_venta_id"],
        "canal": "pdv",
        "modalidad": "takeout",
        "idempotency_key": f"consumo-{uuid.uuid4()}",
        "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
        "tipo": "consumo_personal",
        "consumo_motivo": motivo,
        **extra,
    }
    if autorizacion is not ...:
        if autorizacion is not None:
            cuerpo["autorizacion"] = autorizacion
    else:
        cuerpo["autorizacion"] = _autorizacion(client)
    return client.post("/api/v1/sales/ventas", headers=h, json=cuerpo)


def _configurar_contabilidad(client, h, ids):
    """Cuentas + periodo + la regla que manda el consumo a gasto."""
    hoy = fechas.hoy()
    client.post(
        "/api/v1/accounting/periodos",
        headers=h,
        json={"empresa_id": ids["empresa_id"], "anio": hoy.year, "mes": hoy.month},
    )
    gasto = client.post(
        "/api/v1/accounting/cuentas-contables",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "codigo": "6291",
            "nombre": "Alimentación de personal",
            "tipo": "gasto",
        },
    ).json()
    existencias = client.post(
        "/api/v1/accounting/cuentas-contables",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "codigo": "20",
            "nombre": "Existencias",
            "tipo": "activo",
        },
    ).json()
    client.post(
        "/api/v1/accounting/reglas-asiento",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "evento": "inventory.consumo_personal_valorizado",
            "cuenta_debe_id": gasto["id"],
            "cuenta_haber_id": existencias["id"],
        },
    )
    return gasto["id"], existencias["id"]


# --- Dominio ------------------------------------------------------------------
def test_solo_la_venta_admite_cobro():
    assert rules.admite_cobro("venta")
    assert not rules.admite_cobro("consumo_personal")
    assert rules.es_consumo_personal("consumo_personal")


# --- Venta sin precio ---------------------------------------------------------
def test_consumo_de_personal_nace_en_cero_aunque_el_producto_tenga_precio(env):
    client, ids, TestSession = env
    h = _token(client)
    # Precio de lista vigente: el consumo tiene que ignorarlo, no heredarlo.
    client.post(
        "/api/v1/sales/listas-precio",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "nombre": "General",
            "vigente_desde": fechas.hoy().isoformat(),
            "precios": [{"producto_comercial_id": ids["producto_id"], "precio": "40.00"}],
        },
    )

    r = _crear_consumo(client, h, ids)

    assert r.status_code == 201, r.text
    assert r.json()["tipo"] == "consumo_personal"
    assert r.json()["consumo_motivo"] == "feriado"
    assert Decimal(r.json()["total"]) == Decimal(0)
    with TestSession() as s:
        item = s.scalar(
            select(VentaItem).where(VentaItem.venta_id == uuid.UUID(r.json()["id"]))
        )
        assert item.precio_unitario == Decimal(0)


def test_el_precio_que_mande_el_cliente_no_convierte_el_consumo_en_venta(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_consumo(
        client,
        h,
        ids,
        items=[
            {
                "producto_comercial_id": ids["producto_id"],
                "cantidad": "1",
                "precio_unitario": "40.00",
            }
        ],
    )
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["total"]) == Decimal(0)


def test_sin_autorizacion_del_encargado_no_hay_consumo(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_consumo(client, h, ids, autorizacion=None)
    assert r.status_code == 403


def test_motivo_invalido_se_rechaza(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_consumo(client, h, ids, motivo="porque_si")
    assert r.status_code == 409, r.text


def test_una_venta_normal_no_acepta_motivo_de_consumo(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/sales/ventas",
        headers=h,
        json={
            "sucursal_id": ids["sucursal_id"],
            "punto_venta_id": ids["punto_venta_id"],
            "canal": "pdv",
            "modalidad": "takeout",
            "idempotency_key": f"venta-{uuid.uuid4()}",
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
            "consumo_motivo": "feriado",
        },
    )
    assert r.status_code == 409, r.text


# --- No se cobra --------------------------------------------------------------
def test_un_consumo_de_personal_no_se_cobra(env):
    client, ids, _ = env
    h = _token(client)
    venta = _crear_consumo(client, h, ids).json()

    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/pagos",
        headers=h,
        json={
            "medio_pago_id": ids["medio_id"],
            "monto": "1.00",
            "idempotency_key": f"pago-{uuid.uuid4()}",
        },
    )
    assert r.status_code == 409, r.text
    assert "consumo de personal" in r.json()["detail"]


def test_la_entrega_cierra_el_consumo_sin_pasar_por_caja(env):
    client, ids, TestSession = env
    h = _token(client)
    venta = _crear_consumo(client, h, ids).json()

    # La cocina lo termina: acá no se prueba el KDS, solo su efecto.
    with TestSession() as s:
        for item in s.scalars(
            select(VentaItem).where(VentaItem.venta_id == uuid.UUID(venta["id"]))
        ):
            item.estado_preparacion = "listo"
        s.commit()

    r = client.post(f"/api/v1/sales/ventas/{venta['id']}/entrega", headers=h)
    assert r.status_code == 200, r.text
    with TestSession() as s:
        assert s.get(Venta, uuid.UUID(venta["id"])).estado == "cerrada"


def test_sumar_productos_a_un_consumo_lo_firma_el_encargado(env):
    """Cada aumento es comida regalada más: la firma del alta autorizó ese
    pedido, no los que vengan después (RN-COM-025)."""
    client, ids, _ = env
    h = _token(client)
    venta = _crear_consumo(client, h, ids).json()
    linea = {"producto_comercial_id": ids["producto_id"], "cantidad": "1"}

    sin_firma = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/items",
        headers=h,
        json={"items": [linea]},
    )
    assert sin_firma.status_code == 403, sin_firma.text

    con_firma = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/items",
        headers=h,
        json={"items": [linea], "autorizacion": _autorizacion(client)},
    )
    assert con_firma.status_code == 201, con_firma.text
    items = client.get(f"/api/v1/sales/ventas/{venta['id']}/items", headers=h).json()
    assert len(items) == 2


def test_quitar_una_linea_del_consumo_se_firma_aunque_este_en_la_ventana(env):
    """La ventana de corrección exime al cajero de firmar un tecleo suyo. En
    un consumo no aplica: sacar una línea deshace lo que un encargado ya
    firmó, y el insumo vuelve al almacén (RN-COM-025)."""
    client, ids, _ = env
    h = _token(client)
    venta = _crear_consumo(
        client,
        h,
        ids,
        items=[
            {"producto_comercial_id": ids["producto_id"], "cantidad": "1"},
            {"producto_comercial_id": ids["producto_id"], "cantidad": "1"},
        ],
    ).json()
    items = client.get(f"/api/v1/sales/ventas/{venta['id']}/items", headers=h).json()

    # Recién enviada: en una venta normal esto pasaría sin firma de nadie.
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/anular-lineas",
        headers=h,
        json={"venta_item_ids": [items[0]["id"]], "motivo": "se pidió de más"},
    )
    assert r.status_code == 403, r.text


def test_el_consumo_registrado_viaja_con_lo_que_el_reporte_necesita(env):
    """Sin número de orden ni autorizador, el reporte del turno dice «hubo un
    consumo» y no se puede rastrear contra el pedido que salió de cocina."""
    client, ids, _ = env
    h = _token(client)
    capturados: list[dict] = []
    event_bus.subscribe("sales.consumo_personal_registrado", capturados.append)
    venta = _crear_consumo(client, h, ids).json()

    (payload,) = capturados
    assert payload["numero_orden"] == venta["numero_orden"]
    assert payload["consumo_autorizado_por"]
    assert payload["consumo_motivo"] == "feriado"


# --- Inventario y contabilidad ------------------------------------------------
def test_el_consumo_descuenta_stock_con_su_propio_tipo_de_movimiento(env):
    client, ids, TestSession = env
    h = _token(client)
    venta = _crear_consumo(client, h, ids).json()

    with TestSession() as s:
        stock = s.scalar(
            select(Stock).where(Stock.sku_id == uuid.UUID(ids["sku_id"]))
        )
        assert stock.cantidad == Decimal(100) - INSUMO_POR_PLATO
        movimiento = s.scalar(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia == venta["id"]
            )
        )
        assert movimiento.tipo == "consumo_interno"
        assert movimiento.cantidad == -INSUMO_POR_PLATO


def test_el_costo_del_consumo_llega_a_gasto_de_alimentacion_de_personal(env):
    client, ids, _ = env
    h = _token(client)
    gasto_id, existencias_id = _configurar_contabilidad(client, h, ids)

    venta = _crear_consumo(client, h, ids).json()

    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    generado = [a for a in asientos if a["referencia_origen"] == venta["id"]]
    assert len(generado) == 1
    assert generado[0]["evento_origen"] == "inventory.consumo_personal_valorizado"

    lineas = client.get(
        f"/api/v1/accounting/asientos/{generado[0]['id']}/lineas", headers=h
    ).json()
    por_cuenta = {li["cuenta_contable_id"]: (li["tipo"], Decimal(li["monto"])) for li in lineas}
    assert por_cuenta[gasto_id] == ("debe", COSTO_ESPERADO)
    assert por_cuenta[existencias_id] == ("haber", COSTO_ESPERADO)


def test_una_venta_normal_no_genera_asiento_de_consumo_de_personal(env):
    client, ids, _ = env
    h = _token(client)
    _configurar_contabilidad(client, h, ids)

    venta = client.post(
        "/api/v1/sales/ventas",
        headers=h,
        json={
            "sucursal_id": ids["sucursal_id"],
            "punto_venta_id": ids["punto_venta_id"],
            "canal": "pdv",
            "modalidad": "takeout",
            "idempotency_key": f"venta-{uuid.uuid4()}",
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
        },
    ).json()

    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    assert [a for a in asientos if a["referencia_origen"] == venta["id"]] == []


def test_quitar_una_linea_repone_el_insumo_pero_no_reversa_el_gasto(env):
    """El asiento es de la orden entera: reversarlo por una línea borraría el
    gasto de las que sí se comieron (deuda declarada en ROADMAP)."""
    client, ids, TestSession = env
    h = _token(client)
    _configurar_contabilidad(client, h, ids)
    venta = _crear_consumo(
        client,
        h,
        ids,
        items=[
            {"producto_comercial_id": ids["producto_id"], "cantidad": "1"},
            {"producto_comercial_id": ids["producto_id"], "cantidad": "1"},
        ],
    ).json()
    items = client.get(
        f"/api/v1/sales/ventas/{venta['id']}/items", headers=h
    ).json()

    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/anular-lineas",
        headers=h,
        json={
            "venta_item_ids": [items[0]["id"]],
            "motivo": "sobró comida",
            "autorizacion": _autorizacion(client, "sales.anular"),
        },
    )
    assert r.status_code == 200, r.text

    with TestSession() as s:
        stock = s.scalar(select(Stock).where(Stock.sku_id == uuid.UUID(ids["sku_id"])))
        # Salieron dos platos, volvió uno.
        assert stock.cantidad == Decimal(100) - INSUMO_POR_PLATO
    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    original = [a for a in asientos if a["referencia_origen"] == venta["id"]][0]
    assert original["estado"] == "registrado"


def test_anular_el_consumo_devuelve_el_insumo_y_reversa_el_gasto(env):
    client, ids, TestSession = env
    h = _token(client)
    _configurar_contabilidad(client, h, ids)
    venta = _crear_consumo(client, h, ids).json()

    r = client.post(f"/api/v1/sales/ventas/{venta['id']}/anular", headers=h)
    assert r.status_code == 200, r.text

    with TestSession() as s:
        stock = s.scalar(
            select(Stock).where(Stock.sku_id == uuid.UUID(ids["sku_id"]))
        )
        assert stock.cantidad == Decimal(100)

    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    original = [a for a in asientos if a["referencia_origen"] == venta["id"]][0]
    assert original["estado"] == "anulado"
    assert [a for a in asientos if a.get("asiento_reversa_de_id") == original["id"]]
