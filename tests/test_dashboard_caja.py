"""Ciclo mínimo de caja (PROC-CTB-001/002) y dashboard gerencial: ventas
del día, stock bajo mínimo, cajas abiertas — agregado vía `/api/v1/dashboard/resumen`.

Mismo patrón que test_sales.py: SQLite en memoria, venta/pago reales a
través de la API (no insertados directo), para que la reconciliación de
caja (`total_efectivo_cobrado`) opere sobre datos que pasaron por las
mismas reglas de negocio que en producción.
"""

import time
import uuid
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
from src.modules.accounting.infrastructure.repositories import AperturaCajaRepo
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    Stock,
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
    Almacen,
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
        almacen = Almacen(
            empresa_id=empresa.id, sucursal_id=sucursal.id,
            nombre="Almacén Tarapoto", tipo="sucursal",
        )
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador",
            serie_boleta="B001", serie_factura="F001", politica_pago="adelantado",
        )
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([almacen, pv, udm_cat])
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
            nombre="Pizza base", rendimiento_cantidad=Decimal(1),
            rendimiento_unidad_medida_id=udm.id,
        )
        s.add_all([sku, receta])
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal("0.1")))
        producto = ProductoComercial(
            id_interno="P001", marca_id=marca.id, nombre="Pizza Clásica", receta_id=receta.id,
        )
        medio = MedioPago(
            empresa_id=empresa.id, nombre="Efectivo", direccion="cobro", tipo="efectivo",
        )
        s.add_all([producto, medio])
        s.flush()
        # Precio server-side (RN-PRC-003): sin lista vigente no hay venta.
        lista = ListaPrecio(marca_id=marca.id, nombre="Regular",
                            vigente_desde=date(2020, 1, 1))
        s.add(lista)
        s.flush()
        s.add(Precio(lista_precio_id=lista.id,
                     producto_comercial_id=producto.id, monto=Decimal("50.00")))
        # Stock bajo mínimo a propósito: 1 unidad, mínimo 5 (bandera para el dashboard).
        s.add(
            Stock(
                almacen_id=almacen.id, sku_id=sku.id,
                cantidad=Decimal(1), stock_minimo=Decimal(5),
            )
        )

        cajero = Usuario(username="cajero1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(cajero)
        s.flush()
        rol_cajero = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol_cajero.id))
        # Sin sucursal el JWT sale sin `empresa_id` y todo responde 403 (ADR-004).
        s.add(UsuarioSucursal(usuario_id=cajero.id, sucursal_id=sucursal.id))

        ids.update(
            empresa_id=str(empresa.id), sucursal_id=str(sucursal.id), pv_id=str(pv.id),
            producto_id=str(producto.id), medio_id=str(medio.id), cajero_id=str(cajero.id),
            marca_id=str(marca.id), lista_id=str(lista.id), receta_id=str(receta.id),
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


def _cruzar_segundo() -> None:
    """SQLite guarda `created_at` (`server_default=func.now()`) sin
    microsegundos, pero SQLAlchemy sí los incluye al enlazar un `datetime`
    de Python como parámetro de una consulta — si dos eventos caen en el
    mismo segundo de reloj, la comparación `>=` los compara como texto y
    "...25" < "...25.000000" por ser prefijo, dando un falso negativo.
    Postgres (columna timestamp real, no texto) no tiene este problema.
    Se usa entre `abrir_caja` y la primera venta en los tests que
    reconcilian caja, para no depender de que el runner tarde justo lo
    necesario para cruzar de segundo por su cuenta (flakiness real,
    confirmada: el mismo test pasa solo y falla corriendo con el resto)."""
    time.sleep(1.1)


def _abrir_caja(client, headers, ids, monto="100.00"):
    return client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=headers,
        json={
            "punto_venta_id": ids["pv_id"],
            "relevo_encargado_id": ids["cajero_id"],
            "monto_apertura": monto,
        },
    )


def _producto_a(TestSession, ids, precio):
    """Producto comercial cuyo precio de lista es `precio`.

    El precio ya no viaja en el request (RN-PRC-003), así que un monto
    distinto exige un producto distinto, no un campo distinto.
    """
    if precio == "50.00":
        return ids["producto_id"]
    with TestSession() as s:
        producto = ProductoComercial(
            id_interno=f"P{int(Decimal(precio)):03d}"[:4],
            marca_id=uuid.UUID(ids["marca_id"]),
            nombre=f"Pizza {precio}",
            receta_id=uuid.UUID(ids["receta_id"]),
        )
        s.add(producto)
        s.flush()
        s.add(Precio(
            lista_precio_id=uuid.UUID(ids["lista_id"]),
            producto_comercial_id=producto.id, monto=Decimal(precio),
        ))
        s.commit()
        return str(producto.id)


def _vender_y_cobrar(client, headers, ids, key, precio="50.00",
                     TestSession=None):
    producto_id = (
        _producto_a(TestSession, ids, precio) if TestSession else ids["producto_id"]
    )
    venta = client.post(
        "/api/v1/sales/ventas",
        headers=headers,
        json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": f"venta-{key}",
            "items": [{"producto_comercial_id": producto_id, "cantidad": "1"}],
        },
    ).json()
    client.post(
        f"/api/v1/sales/ventas/{venta['id']}/pagos",
        headers=headers,
        json={"medio_pago_id": ids["medio_id"], "monto": precio, "idempotency_key": f"pago-{key}"},
    )
    return venta


# --- Apertura / cierre de caja ------------------------------------------------
def test_abrir_caja_ok(env):
    client, ids, _ = env
    r = _abrir_caja(client, _token(client), ids)
    assert r.status_code == 201
    assert Decimal(r.json()["monto_apertura"]) == Decimal("100.00")


def test_no_se_puede_abrir_dos_veces_el_mismo_punto_de_venta(env):
    client, ids, _ = env
    h = _token(client)
    assert _abrir_caja(client, h, ids).status_code == 201
    assert _abrir_caja(client, h, ids).status_code == 409


def test_cerrar_caja_sin_ventas_cuadra_exacto(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids).json()
    r = client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/cierre",
        headers=h,
        json={"monto_real": "100.00", "custodia": "local_caja_fuerte"},
    )
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["descuadre_monto"]) == Decimal("0")
    assert body["estado"] == "conforme"


def test_cerrar_caja_reconcilia_ventas_en_efectivo(env):
    """El monto esperado del cierre no es un número tipeado: se calcula
    desde los pagos en efectivo reales de ese punto de venta."""
    client, ids, TestSession = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cruzar_segundo()
    _vender_y_cobrar(client, h, ids, key="0001", precio="50.00")
    _vender_y_cobrar(client, h, ids, key="0002", precio="30.00", TestSession=TestSession)

    r = client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/cierre",
        headers=h,
        json={"monto_real": "180.00", "custodia": "local_caja_fuerte"},
    )
    assert r.status_code == 200
    # 100 apertura + 50 + 30 vendido = 180 esperado; contado 180 → cuadra.
    assert Decimal(r.json()["descuadre_monto"]) == Decimal("0")
    assert r.json()["estado"] == "conforme"


def test_cerrar_caja_con_descuadre_queda_con_irregularidad(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cruzar_segundo()
    _vender_y_cobrar(client, h, ids, key="0003", precio="50.00")

    r = client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/cierre",
        headers=h,
        json={
            "monto_real": "140.00", "custodia": "local_caja_fuerte",
            "descuadre_atribucion": "cajero",
        },
    )
    assert r.status_code == 200
    # Esperado 150 (100+50), contado 140 → falta 10.
    assert Decimal(r.json()["descuadre_monto"]) == Decimal("-10.00")
    assert r.json()["estado"] == "con_irregularidad"


def test_no_se_puede_cerrar_dos_veces_la_misma_apertura(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids).json()
    body = {"monto_real": "100.00", "custodia": "local_caja_fuerte"}
    ruta = f"/api/v1/accounting/cajas/apertura/{apertura['id']}/cierre"
    assert client.post(ruta, headers=h, json=body).status_code == 200
    assert client.post(ruta, headers=h, json=body).status_code == 409


def test_cerrar_caja_inexistente_404(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/accounting/cajas/apertura/00000000-0000-0000-0000-000000000000/cierre",
        headers=h,
        json={"monto_real": "0", "custodia": "local_caja_fuerte"},
    )
    assert r.status_code == 404


def test_cajero_puede_abrir_su_propia_caja(env):
    """El permiso `accounting.caja_operar` (rol cajero) alcanza — no exige
    permisos de administración general."""
    client, ids, _ = env
    h = _token(client, username="cajero1", pin="111111")
    assert _abrir_caja(client, h, ids).status_code == 201


def test_abrir_caja_sin_permiso_403(env):
    client, ids, _ = env
    h = _token(client, username="admin")
    rol_id = client.post(
        "/api/v1/roles", headers=h, json={"nombre": "sin_caja"}
    ).json()["id"]
    usuario_id = client.post(
        "/api/v1/users", headers=h,
        json={"username": "mesero1", "pin": "222222", "tipo": "humano"},
    ).json()["id"]
    client.post(f"/api/v1/users/{usuario_id}/roles", headers=h, json={"rol_id": rol_id})

    h_mesero = _token(client, username="mesero1", pin="222222")
    assert _abrir_caja(client, h_mesero, ids).status_code == 403


# --- Arqueo --------------------------------------------------------------------
def test_arqueo_sin_caja_abierta_404(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/accounting/arqueos", headers=h,
        json={"punto_venta_id": ids["pv_id"], "tipo": "sorpresa", "monto_contado": "0"},
    )
    assert r.status_code == 404


def test_arqueo_con_caja_abierta_calcula_diferencia(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_caja(client, h, ids, monto="100.00")
    r = client.post(
        "/api/v1/accounting/arqueos", headers=h,
        json={"punto_venta_id": ids["pv_id"], "tipo": "sorpresa", "monto_contado": "95.00"},
    )
    assert r.status_code == 201
    assert Decimal(r.json()["diferencia"]) == Decimal("-5.00")


# --- Dashboard -----------------------------------------------------------------
def test_dashboard_resumen_agrega_los_tres_indicadores(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_caja(client, h, ids, monto="100.00")
    _vender_y_cobrar(client, h, ids, key="dash01", precio="50.00")

    r = client.get(
        f"/api/v1/dashboard/resumen?empresa_id={ids['empresa_id']}", headers=h
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ventas_hoy"]["cantidad"] == 1
    assert Decimal(body["ventas_hoy"]["total"]) == Decimal("50.00")
    assert body["stock_bajo_minimo"] == 1  # el Stock del fixture, 1 < mínimo 5
    assert len(body["cajas_abiertas"]) == 1
    assert Decimal(body["cajas_abiertas"][0]["monto_apertura"]) == Decimal("100.00")


def test_dashboard_sin_ventas_ni_caja_da_ceros(env):
    client, ids, _ = env
    h = _token(client)
    r = client.get(
        f"/api/v1/dashboard/resumen?empresa_id={ids['empresa_id']}", headers=h
    )
    body = r.json()
    assert body["ventas_hoy"]["cantidad"] == 0
    assert Decimal(body["ventas_hoy"]["total"]) == Decimal("0")
    assert body["cajas_abiertas"] == []


def test_dashboard_venta_anulada_no_cuenta(env):
    """RN-COM: una orden sin pagar (o anulada) no es ingreso real."""
    client, ids, _ = env
    h = _token(client)
    client.post(
        "/api/v1/sales/ventas", headers=h,
        json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": "venta-sin-pagar",
            "items": [{
                "producto_comercial_id": ids["producto_id"], "cantidad": "1",
            }],
        },
    )
    r = client.get(
        f"/api/v1/dashboard/resumen?empresa_id={ids['empresa_id']}", headers=h
    )
    assert r.json()["ventas_hoy"]["cantidad"] == 0


def test_dashboard_sin_permiso_403(env):
    client, ids, _ = env
    h = _token(client, username="cajero1", pin="111111")
    r = client.get(
        f"/api/v1/dashboard/resumen?empresa_id={ids['empresa_id']}", headers=h
    )
    assert r.status_code == 403


def test_total_efectivo_cobrado_usa_hora_de_apertura_no_desde_siempre(env):
    """Reconciliar desde el inicio de los tiempos sumaría ventas de un
    cajero anterior — el corte es la apertura vigente, no `created_at`
    global de la tabla.

    El pago "antes" se retrasa una hora a mano (UPDATE directo) en vez de
    confiar en que ocurra en un segundo de reloj distinto al de la
    apertura: SQLite guarda `created_at` como texto sin microsegundos
    (`CURRENT_TIMESTAMP`) mientras que el bind de un `datetime` de Python
    sí los lleva — si ambos caen en el mismo segundo, la comparación de
    string de SQLite da falsos negativos que Postgres (tipo timestamp
    real, no texto) no tiene. Retrasar el evento evita pisar ese artefacto
    de la base de pruebas sin depender del reloj real. Se retrasan tanto el
    pago "antes" (-1h) como la apertura misma (-30min) por la misma razón:
    el pago "después" también podría caer en el mismo segundo que la
    apertura si no se separan con margen."""
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from sqlalchemy import update

    from src.modules.accounting.infrastructure.models import AperturaCaja
    from src.modules.sales.application.queries_publicas import total_efectivo_cobrado
    from src.modules.sales.infrastructure.models import Pago

    client, ids, TestSession = env
    h = _token(client)
    ahora = datetime.now(UTC).replace(tzinfo=None)
    _vender_y_cobrar(client, h, ids, key="antes0001", precio="999.00", TestSession=TestSession)
    apertura = _abrir_caja(client, h, ids, monto="0.00").json()
    with TestSession() as s:
        s.execute(
            update(Pago)
            .where(Pago.idempotency_key == "pago-antes0001")
            .values(created_at=ahora - timedelta(hours=1))
        )
        s.execute(
            update(AperturaCaja)
            .where(AperturaCaja.id == UUID(apertura["id"]))
            .values(created_at=ahora - timedelta(minutes=30))
        )
        s.commit()
    _vender_y_cobrar(client, h, ids, key="despues01", precio="10.00", TestSession=TestSession)

    with TestSession() as s:
        corte = AperturaCajaRepo(s).get(UUID(apertura["id"])).created_at
        total = total_efectivo_cobrado(s, UUID(ids["pv_id"]), corte)
    assert total == Decimal("10.00")
