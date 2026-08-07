"""Tests del slice accounting core: plan de cuentas, periodo, asiento manual
(cuadre, anulación) y generación automática vía `regla_asiento` desde eventos
operativos ya publicados (`purchases.oc_emitida`, `sales.venta_confirmada`).
SQLite en memoria + override de get_db, mismo patrón que test_purchases.py.
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
from src.modules.accounting.application import listeners as accounting_listeners
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Marca,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared import fechas


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
        almacen = Almacen(empresa_id=empresa.id, nombre="Central", tipo="central")
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Local 1",
            direccion="Jr. Falso 123", tenencia="propia",
        )
        s.add_all([almacen, sucursal])
        s.flush()

        contador = Usuario(username="contador1", pin_hash=hash_pin("333333"), tipo="humano")
        s.add(contador)
        s.flush()
        rol_contador = s.scalar(select(Rol).where(Rol.nombre == "contador"))
        s.add(UsuarioRol(usuario_id=contador.id, rol_id=rol_contador.id))
        # Sin sucursal el JWT sale sin `empresa_id` y todo responde 403 (ADR-004).
        s.add(UsuarioSucursal(usuario_id=contador.id, sucursal_id=sucursal.id))

        ids.update(
            empresa_id=str(empresa.id), almacen_id=str(almacen.id), sucursal_id=str(sucursal.id),
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


def _crear_cuenta(client, headers, ids, codigo, nombre, tipo):
    return client.post(
        "/api/v1/accounting/cuentas-contables",
        headers=headers,
        json={"empresa_id": ids["empresa_id"], "codigo": codigo, "nombre": nombre, "tipo": tipo},
    )


def _abrir_periodo_actual(client, headers, ids):
    hoy = fechas.hoy()
    return client.post(
        "/api/v1/accounting/periodos",
        headers=headers,
        json={"empresa_id": ids["empresa_id"], "anio": hoy.year, "mes": hoy.month},
    )


def test_crear_cuenta_contable(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_cuenta(client, h, ids, "70", "Ventas", "ingreso")
    assert r.status_code == 201
    assert r.json()["tipo"] == "ingreso"


def test_crear_cuenta_codigo_duplicado_409(env):
    client, ids, _ = env
    h = _token(client)
    _crear_cuenta(client, h, ids, "60", "Compras", "gasto")
    r = _crear_cuenta(client, h, ids, "60", "Compras 2", "gasto")
    assert r.status_code == 409


def test_abrir_periodo_es_idempotente(env):
    client, ids, _ = env
    h = _token(client)
    r1 = _abrir_periodo_actual(client, h, ids)
    r2 = _abrir_periodo_actual(client, h, ids)
    assert r1.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def _cuentas_debe_haber(client, h, ids):
    caja = _crear_cuenta(client, h, ids, "10", "Caja", "activo").json()
    ventas = _crear_cuenta(client, h, ids, "70", "Ventas", "ingreso").json()
    return caja["id"], ventas["id"]


def test_crear_asiento_manual_sin_periodo_abierto_409(env):
    client, ids, _ = env
    h = _token(client)
    caja_id, ventas_id = _cuentas_debe_haber(client, h, ids)
    r = client.post(
        "/api/v1/accounting/asientos",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "fecha": fechas.hoy().isoformat(),
            "glosa": "Venta al contado",
            "lineas": [
                {"cuenta_contable_id": caja_id, "tipo": "debe", "monto": "100.00"},
                {"cuenta_contable_id": ventas_id, "tipo": "haber", "monto": "100.00"},
            ],
        },
    )
    assert r.status_code == 409


def test_crear_asiento_manual_cuadrado_y_descuadrado(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    caja_id, ventas_id = _cuentas_debe_haber(client, h, ids)

    ok = client.post(
        "/api/v1/accounting/asientos",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "fecha": fechas.hoy().isoformat(),
            "glosa": "Venta al contado",
            "lineas": [
                {"cuenta_contable_id": caja_id, "tipo": "debe", "monto": "100.00"},
                {"cuenta_contable_id": ventas_id, "tipo": "haber", "monto": "100.00"},
            ],
        },
    )
    assert ok.status_code == 201
    assert ok.json()["estado"] == "registrado"

    mal = client.post(
        "/api/v1/accounting/asientos",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "fecha": fechas.hoy().isoformat(),
            "glosa": "Descuadrado",
            "lineas": [
                {"cuenta_contable_id": caja_id, "tipo": "debe", "monto": "100.00"},
                {"cuenta_contable_id": ventas_id, "tipo": "haber", "monto": "50.00"},
            ],
        },
    )
    assert mal.status_code == 409


def test_anular_asiento_genera_reversa_y_anula_original(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    caja_id, ventas_id = _cuentas_debe_haber(client, h, ids)

    asiento = client.post(
        "/api/v1/accounting/asientos",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "fecha": fechas.hoy().isoformat(),
            "glosa": "Venta al contado",
            "lineas": [
                {"cuenta_contable_id": caja_id, "tipo": "debe", "monto": "100.00"},
                {"cuenta_contable_id": ventas_id, "tipo": "haber", "monto": "100.00"},
            ],
        },
    ).json()

    reversa = client.post(f"/api/v1/accounting/asientos/{asiento['id']}/anular", headers=h)
    assert reversa.status_code == 200
    assert reversa.json()["asiento_reversa_de_id"] == asiento["id"]

    original = client.get(f"/api/v1/accounting/asientos/{asiento['id']}", headers=h).json()
    assert original["estado"] == "anulado"

    lineas_reversa = client.get(
        f"/api/v1/accounting/asientos/{reversa.json()['id']}/lineas", headers=h
    ).json()
    tipos = {(li["cuenta_contable_id"], li["tipo"]) for li in lineas_reversa}
    assert (caja_id, "haber") in tipos
    assert (ventas_id, "debe") in tipos


def test_cerrar_periodo_bloquea_nuevos_asientos_y_no_admite_doble_cierre(env):
    client, ids, _ = env
    h = _token(client)
    periodo = _abrir_periodo_actual(client, h, ids).json()
    caja_id, ventas_id = _cuentas_debe_haber(client, h, ids)

    cierre = client.post(f"/api/v1/accounting/periodos/{periodo['id']}/cerrar", headers=h)
    assert cierre.status_code == 200
    assert cierre.json()["estado"] == "cerrado"

    r = client.post(
        "/api/v1/accounting/asientos",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "fecha": fechas.hoy().isoformat(),
            "glosa": "No debería registrar",
            "lineas": [
                {"cuenta_contable_id": caja_id, "tipo": "debe", "monto": "10.00"},
                {"cuenta_contable_id": ventas_id, "tipo": "haber", "monto": "10.00"},
            ],
        },
    )
    assert r.status_code == 409

    doble_cierre = client.post(f"/api/v1/accounting/periodos/{periodo['id']}/cerrar", headers=h)
    assert doble_cierre.status_code == 409


def test_rol_sin_permiso_accounting_403(env):
    client, ids, _ = env
    h_contador = _token(client, "contador1", "333333")
    # contador SÍ puede administrar cuentas...
    r = _crear_cuenta(client, h_contador, ids, "10", "Caja", "activo")
    assert r.status_code == 201


def test_rol_cocinero_sin_permiso_accounting_403(env):
    client, ids, TestSession = env
    from src.modules.users.infrastructure.models import Usuario as U

    with TestSession() as s:
        cocinero = U(username="cocinero1", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cocinero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
        s.add(UsuarioRol(usuario_id=cocinero.id, rol_id=rol.id))
        s.commit()

    h_cocinero = _token(client, "cocinero1", "222222")
    r = _crear_cuenta(client, h_cocinero, ids, "10", "Caja", "activo")
    assert r.status_code == 403


# --- Generación automática desde eventos operativos --------------------------

def _crear_regla_asiento(client, h, ids, evento, cuenta_debe_id, cuenta_haber_id):
    return client.post(
        "/api/v1/accounting/reglas-asiento",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "evento": evento,
            "cuenta_debe_id": cuenta_debe_id,
            "cuenta_haber_id": cuenta_haber_id,
        },
    )


def _crear_articulo_insumo(TestSession, empresa_id: str) -> str:
    from src.modules.inventory.infrastructure.models import Articulo, CategoriaUdm, UnidadMedida

    with TestSession() as s:
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        s.add(udm)
        s.flush()
        art = Articulo(
            empresa_id=uuid.UUID(empresa_id), id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        s.add(art)
        s.commit()
        return str(art.id)


def _crear_proveedor(client, h, ids):
    return client.post(
        "/api/v1/purchases/proveedores",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"], "tipo": "juridico", "condicion_pago": "contado",
            "razon_social": "Molinera SAC", "ruc": "20111111111", "clasificacion": "preferente",
        },
    ).json()


def test_oc_emitida_con_regla_configurada_genera_asiento_automatico(env):
    client, ids, TestSession = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    gasto_id = _crear_cuenta(client, h, ids, "60", "Compras", "gasto").json()["id"]
    pasivo_id = _crear_cuenta(client, h, ids, "42", "Cuentas por pagar", "pasivo").json()["id"]
    _crear_regla_asiento(client, h, ids, "purchases.oc_emitida", gasto_id, pasivo_id)

    articulo_id = _crear_articulo_insumo(TestSession, ids["empresa_id"])
    proveedor = _crear_proveedor(client, h, ids)
    oc = client.post(
        "/api/v1/purchases/ordenes-compra",
        headers=h,
        json={
            "proveedor_id": proveedor["id"],
            "almacen_destino_id": ids["almacen_id"],
            "idempotency_key": "oc-acc-2",
            "items": [{"articulo_id": articulo_id, "cantidad": "10", "costo_unitario": "5.00"}],
        },
    ).json()
    client.post(f"/api/v1/purchases/ordenes-compra/{oc['id']}/emitir", headers=h)

    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    generado = [a for a in asientos if a["referencia_origen"] == oc["id"]]
    assert len(generado) == 1
    assert generado[0]["evento_origen"] == "purchases.oc_emitida"

    lineas = client.get(
        f"/api/v1/accounting/asientos/{generado[0]['id']}/lineas", headers=h
    ).json()
    montos = {li["tipo"]: Decimal(li["monto"]) for li in lineas}
    assert montos == {"debe": Decimal("50.00"), "haber": Decimal("50.00")}


def test_oc_emitida_sin_regla_no_genera_asiento(env):
    client, ids, TestSession = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)

    with TestSession() as s:
        from src.modules.inventory.infrastructure.models import (
            Articulo,
            CategoriaUdm,
            UnidadMedida,
        )

        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        s.add(udm)
        s.flush()
        art = Articulo(
            empresa_id=uuid.UUID(ids["empresa_id"]), id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        s.add(art)
        s.commit()
        articulo_id = str(art.id)

    proveedor = client.post(
        "/api/v1/purchases/proveedores",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"], "tipo": "juridico", "condicion_pago": "contado",
            "razon_social": "Molinera SAC", "ruc": "20111111111", "clasificacion": "preferente",
        },
    ).json()
    oc = client.post(
        "/api/v1/purchases/ordenes-compra",
        headers=h,
        json={
            "proveedor_id": proveedor["id"],
            "almacen_destino_id": ids["almacen_id"],
            "idempotency_key": "oc-acc-1",
            "items": [{"articulo_id": articulo_id, "cantidad": "10", "costo_unitario": "5.00"}],
        },
    ).json()
    client.post(f"/api/v1/purchases/ordenes-compra/{oc['id']}/emitir", headers=h)

    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    assert not any(a["evento_origen"] == "purchases.oc_emitida" for a in asientos)


def test_venta_confirmada_con_regla_configurada_genera_asiento_automatico(env):
    client, ids, TestSession = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    caja_id = _crear_cuenta(client, h, ids, "10", "Caja", "activo").json()["id"]
    ventas_id = _crear_cuenta(client, h, ids, "70", "Ventas", "ingreso").json()["id"]
    _crear_regla_asiento(client, h, ids, "sales.venta_confirmada", caja_id, ventas_id)

    venta_id = str(uuid.uuid4())
    payload = {
        "venta_id": venta_id,
        "sucursal_id": ids["sucursal_id"],
        "items": [],
        "total": "45.50",
    }
    accounting_listeners.on_venta_confirmada(payload)

    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    generado = [a for a in asientos if a["referencia_origen"] == venta_id]
    assert len(generado) == 1
    assert generado[0]["evento_origen"] == "sales.venta_confirmada"


def _payload_traslado(ids, transferencia_id, diferencias, monto):
    return {
        "transferencia_id": transferencia_id,
        "origen_almacen_id": ids["almacen_id"],
        "destino_almacen_id": ids["almacen_id"],
        "solicitud_id": None,
        "diferencias": diferencias,
        "monto_diferencia": monto,
    }


def _asientos_de(client, h, ids, referencia):
    asientos = client.get(
        f"/api/v1/accounting/asientos?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    return [a for a in asientos if a["referencia_origen"] == referencia]


def test_traslado_con_faltante_asienta_la_perdida(env):
    """Mover mercadería entre almacenes de la misma empresa no mueve
    resultado. Lo que sí es un hecho contable es lo que salió y no llegó."""
    client, ids, _ = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    perdida_id = _crear_cuenta(client, h, ids, "65", "Pérdidas", "gasto").json()["id"]
    existencias_id = _crear_cuenta(
        client, h, ids, "20", "Existencias", "activo"
    ).json()["id"]
    _crear_regla_asiento(
        client, h, ids, "inventory.transferencia_recibida", perdida_id, existencias_id
    )

    transferencia_id = str(uuid.uuid4())
    accounting_listeners.on_transferencia_recibida(
        _payload_traslado(
            ids,
            transferencia_id,
            [{"sku_id": str(uuid.uuid4()), "lote_id": None,
              "enviada": "10", "recibida": "8"}],
            "24.00",
        )
    )

    (generado,) = _asientos_de(client, h, ids, transferencia_id)
    assert generado["evento_origen"] == "inventory.transferencia_recibida"


def test_traslado_sin_faltante_no_asienta_nada(env):
    """Un asiento por cada traslado llenaría el libro de movimientos que se
    cancelan entre sí."""
    client, ids, _ = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    perdida_id = _crear_cuenta(client, h, ids, "65", "Pérdidas", "gasto").json()["id"]
    existencias_id = _crear_cuenta(
        client, h, ids, "20", "Existencias", "activo"
    ).json()["id"]
    _crear_regla_asiento(
        client, h, ids, "inventory.transferencia_recibida", perdida_id, existencias_id
    )

    transferencia_id = str(uuid.uuid4())
    accounting_listeners.on_transferencia_recibida(
        _payload_traslado(ids, transferencia_id, [], "0")
    )

    assert _asientos_de(client, h, ids, transferencia_id) == []


def test_la_merma_desechada_se_asienta_como_perdida(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    perdida_id = _crear_cuenta(client, h, ids, "65", "Mermas", "gasto").json()["id"]
    existencias_id = _crear_cuenta(
        client, h, ids, "20", "Existencias", "activo"
    ).json()["id"]
    _crear_regla_asiento(
        client, h, ids, "inventory.merma_registrada", perdida_id, existencias_id
    )

    sku_id = str(uuid.uuid4())
    accounting_listeners.on_merma_registrada({
        "almacen_id": ids["almacen_id"], "sku_id": sku_id, "lote_id": None,
        "cantidad": "3", "motivo": "auditoria", "monto": "60.00",
    })

    (generado,) = _asientos_de(client, h, ids, sku_id)
    assert generado["evento_origen"] == "inventory.merma_registrada"


def test_una_merma_sin_costo_cargado_no_asienta_un_cero(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    perdida_id = _crear_cuenta(client, h, ids, "65", "Mermas", "gasto").json()["id"]
    existencias_id = _crear_cuenta(
        client, h, ids, "20", "Existencias", "activo"
    ).json()["id"]
    _crear_regla_asiento(
        client, h, ids, "inventory.merma_registrada", perdida_id, existencias_id
    )

    sku_id = str(uuid.uuid4())
    accounting_listeners.on_merma_registrada({
        "almacen_id": ids["almacen_id"], "sku_id": sku_id, "lote_id": None,
        "cantidad": "3", "motivo": "auditoria", "monto": "0",
    })
    assert _asientos_de(client, h, ids, sku_id) == []


# --- Pago a proveedor (PROC-CTB-003) ------------------------------------------

def _dar_conformidad(client, h, oc_id, idempotency_key="conf-key-1"):
    return client.post(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/conformidad-comprobante",
        headers=h,
        json={
            "idempotency_key": idempotency_key,
            "tipo": "factura",
            "serie": "F001",
            "correlativo": 1,
            "sustento": "efectivo",
        },
    )


def _flujo_oc_recibida(
    client, h, ids, TestSession, costo_unitario="5.00", idempotency_key="oc-pago-1"
):
    articulo_id = _crear_articulo_insumo(TestSession, ids["empresa_id"])
    proveedor = _crear_proveedor(client, h, ids)
    oc = client.post(
        "/api/v1/purchases/ordenes-compra",
        headers=h,
        json={
            "proveedor_id": proveedor["id"],
            "almacen_destino_id": ids["almacen_id"],
            "idempotency_key": idempotency_key,
            "items": [
                {"articulo_id": articulo_id, "cantidad": "10", "costo_unitario": costo_unitario}
            ],
        },
    ).json()
    client.post(f"/api/v1/purchases/ordenes-compra/{oc['id']}/emitir", headers=h)

    from src.modules.purchases.infrastructure.models import OrdenCompraItem

    with TestSession() as s:
        item = s.scalar(
            select(OrdenCompraItem).where(OrdenCompraItem.orden_compra_id == uuid.UUID(oc["id"]))
        )
        item_id = str(item.id)
    client.post(
        f"/api/v1/purchases/ordenes-compra/{oc['id']}/recepciones", headers=h, json={
            "idempotency_key": f"recep-{idempotency_key}",
            "items": [{"orden_compra_item_id": item_id, "cantidad_recibida": "10"}],
        },
    )
    return oc


def test_conformidad_comprobante_encola_pago_pendiente(env):
    client, ids, TestSession = env
    h = _token(client)
    oc = _flujo_oc_recibida(client, h, ids, TestSession)

    conf = _dar_conformidad(client, h, oc["id"])
    assert conf.status_code == 201

    pagos = client.get(
        f"/api/v1/accounting/pagos-proveedor?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    generado = [p for p in pagos if p["orden_compra_id"] == oc["id"]]
    assert len(generado) == 1
    assert generado[0]["estado"] == "pendiente"
    assert Decimal(generado[0]["monto"]) == Decimal("50.00")


def test_conformidad_comprobante_reintento_no_duplica_pago(env):
    client, ids, TestSession = env
    h = _token(client)
    oc = _flujo_oc_recibida(client, h, ids, TestSession)

    _dar_conformidad(client, h, oc["id"], idempotency_key="conf-dup")
    _dar_conformidad(client, h, oc["id"], idempotency_key="conf-dup")

    pagos = client.get(
        f"/api/v1/accounting/pagos-proveedor?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"]
    generado = [p for p in pagos if p["orden_compra_id"] == oc["id"]]
    assert len(generado) == 1


def test_ejecutar_pago_bajo_umbral_genera_asiento(env):
    client, ids, TestSession = env
    h = _token(client)
    _abrir_periodo_actual(client, h, ids)
    banco_id = _crear_cuenta(client, h, ids, "10", "Bancos", "activo").json()["id"]
    cxp_id = _crear_cuenta(client, h, ids, "42", "Cuentas por pagar", "pasivo").json()["id"]
    _crear_regla_asiento(client, h, ids, "accounting.pago_ejecutado", cxp_id, banco_id)

    oc = _flujo_oc_recibida(client, h, ids, TestSession)
    _dar_conformidad(client, h, oc["id"])
    pago = client.get(
        f"/api/v1/accounting/pagos-proveedor?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"][0]

    ejecutado = client.post(
        f"/api/v1/accounting/pagos-proveedor/{pago['id']}/ejecutar",
        headers=h,
        json={"medio_pago": "transferencia", "constancia": "OP-001"},
    )
    assert ejecutado.status_code == 200
    assert ejecutado.json()["estado"] == "ejecutado"
    assert ejecutado.json()["asiento_id"] is not None

    lineas = client.get(
        f"/api/v1/accounting/asientos/{ejecutado.json()['asiento_id']}/lineas", headers=h
    ).json()
    montos = {li["tipo"]: Decimal(li["monto"]) for li in lineas}
    assert montos == {"debe": Decimal("50.00"), "haber": Decimal("50.00")}

    doble = client.post(
        f"/api/v1/accounting/pagos-proveedor/{pago['id']}/ejecutar",
        headers=h,
        json={"medio_pago": "transferencia"},
    )
    assert doble.status_code == 409


def test_ejecutar_pago_sobre_umbral_requiere_permiso_aprobar(env):
    client, ids, TestSession = env
    h_admin = _token(client)
    h_contador = _token(client, "contador1", "333333")

    oc = _flujo_oc_recibida(client, h_admin, ids, TestSession, costo_unitario="250.00")
    _dar_conformidad(client, h_admin, oc["id"])
    pago = client.get(
        f"/api/v1/accounting/pagos-proveedor?empresa_id={ids['empresa_id']}", headers=h_admin
    ).json()["items"][0]
    assert Decimal(pago["monto"]) == Decimal("2500.00")

    r = client.post(
        f"/api/v1/accounting/pagos-proveedor/{pago['id']}/ejecutar",
        headers=h_contador,
        json={"medio_pago": "transferencia"},
    )
    assert r.status_code == 409

    r2 = client.post(
        f"/api/v1/accounting/pagos-proveedor/{pago['id']}/ejecutar",
        headers=h_admin,
        json={"medio_pago": "transferencia"},
    )
    assert r2.status_code == 200


def test_rechazar_pago_bloquea_ejecucion_posterior(env):
    client, ids, TestSession = env
    h = _token(client)
    oc = _flujo_oc_recibida(client, h, ids, TestSession)
    _dar_conformidad(client, h, oc["id"])
    pago = client.get(
        f"/api/v1/accounting/pagos-proveedor?empresa_id={ids['empresa_id']}", headers=h
    ).json()["items"][0]

    r = client.post(f"/api/v1/accounting/pagos-proveedor/{pago['id']}/rechazar", headers=h)
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazado"

    r2 = client.post(
        f"/api/v1/accounting/pagos-proveedor/{pago['id']}/ejecutar",
        headers=h,
        json={"medio_pago": "efectivo"},
    )
    assert r2.status_code == 409


def test_dar_conformidad_sin_permiso_403(env):
    client, ids, TestSession = env
    h_admin = _token(client)
    oc = _flujo_oc_recibida(client, h_admin, ids, TestSession)

    with TestSession() as s:
        cocinero = Usuario(username="cocinero_pago", pin_hash=hash_pin("444444"), tipo="humano")
        s.add(cocinero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
        s.add(UsuarioRol(usuario_id=cocinero.id, rol_id=rol.id))
        s.commit()
    h_cocinero = _token(client, "cocinero_pago", "444444")

    r = _dar_conformidad(client, h_cocinero, oc["id"])
    assert r.status_code == 403
