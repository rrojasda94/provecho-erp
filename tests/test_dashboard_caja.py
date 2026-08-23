"""Ciclo mínimo de caja (PROC-CTB-001/002) y dashboard gerencial: ventas
del día, stock bajo mínimo, cajas abiertas — agregado vía `/api/v1/dashboard/resumen`.

Mismo patrón que test_sales.py: SQLite en memoria, venta/pago reales a
través de la API (no insertados directo), para que la reconciliación de
caja (`total_efectivo_cobrado`) opere sobre datos que pasaron por las
mismas reglas de negocio que en producción.
"""

import time
import uuid
from datetime import UTC, date, datetime
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
from tests.conftest import billetes


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
            empresa_id=empresa.id,
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

        cajero = Usuario(username="cajero_test", pin_hash=hash_pin("111111"), tipo="humano")
        # La cadena de custodia necesita dos personas: el cajero, que deja
        # el efectivo contado en el cajón al cerrar, y el encargado, que
        # firma con su PIN haberlo recibido (RN-MDP-002/008).
        encargado = Usuario(
            username="encargado1", pin_hash=hash_pin("222222"), tipo="humano"
        )
        s.add_all([cajero, encargado])
        s.flush()
        rol_cajero = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        rol_sup = s.scalar(select(Rol).where(Rol.nombre == "supervisor"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol_cajero.id))
        s.add(UsuarioRol(usuario_id=encargado.id, rol_id=rol_sup.id))
        # Sin sucursal el JWT sale sin `empresa_id` y todo responde 403 (ADR-004).
        s.add(UsuarioSucursal(usuario_id=cajero.id, sucursal_id=sucursal.id))
        s.add(UsuarioSucursal(usuario_id=encargado.id, sucursal_id=sucursal.id))

        ids.update(
            empresa_id=str(empresa.id), sucursal_id=str(sucursal.id), pv_id=str(pv.id),
            producto_id=str(producto.id), medio_id=str(medio.id), cajero_id=str(cajero.id),
            encargado_id=str(encargado.id),
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


def _autorizacion(client, permiso, username="encargado1", pin="222222"):
    """Elevación de PIN del encargado: es quien firma cada tramo de la
    cadena de custodia (RN-MDP-002), no el cajero desde su propia sesión.

    Abrir y cerrar **ya no la usan** (RN-MDP-008): son actos del cajero con
    su sola sesión. Queda para entregar el efectivo, autorizar un retiro del
    cajón y reabrir un cierre.
    """
    r = client.post(
        "/api/v1/auth/autorizar",
        json={"username": username, "pin": pin, "permiso": permiso},
    )
    assert r.status_code == 200, r.text
    return r.json()["autorizacion"]


def _abrir_caja(client, headers, ids, monto="100.00", declarado=None):
    return client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=headers,
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": declarado or monto,
            "detalle_denominaciones": billetes(monto),
        },
    )


def _cerrar_caja(client, headers, apertura_id, monto, **extra):
    return client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura_id}/cierre",
        headers=headers,
        json={
            "detalle_denominaciones": billetes(monto),
            "custodia": "local_caja_fuerte",
            **extra,
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
    r = _cerrar_caja(client, h, apertura["id"], "100.00")
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

    r = _cerrar_caja(client, h, apertura["id"], "180.00")
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

    r = _cerrar_caja(
        client, h, apertura["id"], "140.00", descuadre_atribucion="cajero"
    )
    assert r.status_code == 200
    # Esperado 150 (100+50), contado 140 → falta 10.
    assert Decimal(r.json()["descuadre_monto"]) == Decimal("-10.00")
    assert r.json()["estado"] == "con_irregularidad"


def test_no_se_puede_cerrar_dos_veces_la_misma_apertura(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids).json()
    assert _cerrar_caja(client, h, apertura["id"], "100.00").status_code == 200
    assert _cerrar_caja(client, h, apertura["id"], "100.00").status_code == 409


def test_cerrar_caja_inexistente_404(env):
    client, ids, _ = env
    h = _token(client)
    r = _cerrar_caja(
        client, h, "00000000-0000-0000-0000-000000000000", "0.00"
    )
    assert r.status_code == 404


def test_cajero_puede_abrir_su_propia_caja(env):
    """El permiso `accounting.caja_operar` (rol cajero) alcanza — no exige
    permisos de administración general."""
    client, ids, _ = env
    h = _token(client, username="cajero_test", pin="111111")
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
    h = _token(client, username="cajero_test", pin="111111")
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
    # El cobro "de antes" pertenece al turno anterior: se cobra con esa caja
    # abierta y recién después se cierra, que es la secuencia real ahora que
    # cobrar exige turno (RN-MDP-002).
    turno_anterior = _abrir_caja(client, h, ids, monto="0.00").json()
    _vender_y_cobrar(client, h, ids, key="antes0001", precio="999.00", TestSession=TestSession)
    _cerrar_caja(client, h, turno_anterior["id"], "999.00")
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


def test_el_cajero_ve_la_caja_abierta_de_su_sucursal(env):
    """El PDV pregunta "¿mi caja ya está abierta?" antes de ofrecer abrirla.

    `GET /cajas/abiertas` exigía `accounting.leer`, que el rol `cajero` no
    tiene ni le corresponde —es el permiso de todo el módulo contable—, así
    que recibía 403. El PDV lo leía como "no hay caja", pedía la apertura, y
    la apertura rebotaba con "ya hay una caja abierta": el cajero quedaba sin
    poder vender ni entender por qué.

    Acotado a **su** sucursal: quien opera una caja no tiene por qué ver el
    efectivo de los demás locales.
    """
    client, ids, _ = env
    admin = _token(client)
    abierta = _abrir_caja(client, admin, ids).json()

    cajero = _token(client, "cajero_test", "111111")
    suya = client.get(
        f"/api/v1/accounting/cajas/abiertas?sucursal_id={ids['sucursal_id']}",
        headers=cajero,
    )
    assert suya.status_code == 200, suya.text
    assert [c["apertura_caja_id"] for c in suya.json()] == [abierta["id"]]

    # Sin acotar es la empresa entera, y eso sí es `accounting.leer`.
    assert client.get("/api/v1/accounting/cajas/abiertas", headers=cajero).status_code == 403
    assert client.get("/api/v1/accounting/cajas/abiertas", headers=admin).status_code == 200


def test_no_se_ve_la_caja_de_una_sucursal_ajena(env):
    """El alcance lo pone el tenant, no la confianza en el parámetro: pedir
    otra sucursal no es "ver menos", es un 403 (ADR-004)."""
    client, ids, TestSession = env
    with TestSession() as s:
        otra = Sucursal(
            empresa_id=uuid.UUID(ids["empresa_id"]),
            marca_id=uuid.UUID(ids["marca_id"]),
            nombre="Ajena",
            direccion="Otro distrito 123",
            estado="activa",
            tenencia="propia",
        )
        s.add(otra)
        s.commit()
        ajena_id = str(otra.id)

    cajero = _token(client, "cajero_test", "111111")
    r = client.get(
        f"/api/v1/accounting/cajas/abiertas?sucursal_id={ajena_id}", headers=cajero
    )
    assert r.status_code == 403, r.text


def test_el_cajero_anula_lo_recien_enviado_y_despues_necesita_firma(env):
    """El botón "Anular pedido" del PDV devolvía 403 al cajero y el pedido
    quedaba en cocina.

    Ahora hay dos tramos (RN-COM-029): dentro de los 5 minutos la anula el
    cajero solo —es corregir un tecleo, el plato todavía no se armó— y
    después hace falta la firma de un supervisor, igual que para quitar una
    línea (RN-COM-020).
    """
    from datetime import timedelta

    from sqlalchemy import update

    from src.modules.sales.infrastructure.models import VentaItem

    client, ids, TestSession = env
    cajero = _token(client, "cajero_test", "111111")

    def vender(key):
        r = client.post(
            "/api/v1/sales/ventas",
            headers=cajero,
            json={
                "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
                "canal": "pdv", "modalidad": "takeout", "idempotency_key": key,
                "items": [
                    {"producto_comercial_id": ids["producto_id"], "cantidad": "1"}
                ],
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    # Recién enviada: el cajero la anula solo.
    reciente = vender("anu-0001")
    r = client.post(f"/api/v1/sales/ventas/{reciente}/anular", headers=cajero)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "anulada"

    # Vieja: el mismo cajero ya no puede, y el mensaje dice por qué.
    vieja = vender("anu-0002")
    with TestSession() as s:
        s.execute(
            update(VentaItem)
            .where(VentaItem.venta_id == uuid.UUID(vieja))
            .values(created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=30))
        )
        s.commit()

    sin_firma = client.post(f"/api/v1/sales/ventas/{vieja}/anular", headers=cajero)
    assert sin_firma.status_code == 403, sin_firma.text
    assert "supervisor" in sin_firma.json()["detail"]

    con_firma = client.post(
        f"/api/v1/sales/ventas/{vieja}/anular",
        headers=cajero,
        json={"autorizacion": _autorizacion(client, "sales.anular")},
    )
    assert con_firma.status_code == 200, con_firma.text
    assert con_firma.json()["estado"] == "anulada"


def test_el_supervisor_anula_sin_tener_que_firmarse_a_si_mismo(env):
    """Quien ya tiene el permiso no teclea su propio PIN: pedirle la firma
    para anular su propio pedido sería trabajo sin ninguna garantía extra."""
    client, ids, _ = env
    # La venta la crea el cajero: `supervisor` no tiene `sales.crear` ni
    # `sales.cobrar`. Que los dos roles sean disjuntos es justamente por qué
    # el endpoint acepta uno **u** otro y no los dos.
    cajero = _token(client, "cajero_test", "111111")
    supervisor = _token(client, "encargado1", "222222")
    venta = client.post(
        "/api/v1/sales/ventas",
        headers=cajero,
        json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": "anu-0002",
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
        },
    ).json()

    r = client.post(f"/api/v1/sales/ventas/{venta['id']}/anular", headers=supervisor)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "anulada"


def test_una_orden_enviada_admite_lineas_nuevas_sin_permiso_extra(env):
    """Una mesa pide de a poco (RN-COM-029): la segunda ronda va a la misma
    orden, no a una nueva que después se cobra y se entrega por separado.

    Agregar no pide firma de nadie — es lo que el negocio quiere que pase —
    y el evento lleva **solo lo agregado**: si llevara el total acumulado,
    contabilidad asentaría la venta dos veces.
    """
    from src.core.events import event_bus

    client, ids, TestSession = env
    publicados: list[dict] = []
    event_bus.subscribe("sales.venta_confirmada", publicados.append)
    cajero = _token(client, "cajero_test", "111111")
    venta = client.post(
        "/api/v1/sales/ventas",
        headers=cajero,
        json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "mesa", "idempotency_key": "add-0001",
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
        },
    ).json()
    assert Decimal(venta["total"]) == Decimal("50.00")

    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/items",
        headers=cajero,
        json={"items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "2"}]},
    )
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["total"]) == Decimal("150.00")
    assert r.json()["estado"] == "orden"
    assert len(client.get(
        f"/api/v1/sales/ventas/{venta['id']}/items", headers=cajero
    ).json()) == 2

    # El evento lleva lo agregado (100), no el acumulado (150): accounting
    # asienta `total`, y mandarle el acumulado contaría la venta dos veces.
    assert [p["total"] for p in publicados] == ["50.00", "100.00"]
    # Y solo el detalle de lo nuevo, para que inventory no vuelva a descontar
    # lo que ya descontó.
    assert len(publicados[-1]["items"]) == 1


def test_no_se_agregan_lineas_a_una_orden_ya_cobrada(env):
    """Después del cobro la cuenta está cerrada: lo que venga es otra orden.
    Dejar crecer una venta pagada dejaría el comprobante corto."""
    client, ids, _ = env
    admin = _token(client)
    _abrir_caja(client, admin, ids)
    venta = client.post(
        "/api/v1/sales/ventas",
        headers=admin,
        json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": "add-0002",
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
        },
    ).json()
    client.post(
        f"/api/v1/sales/ventas/{venta['id']}/pagos",
        headers=admin,
        json={
            "medio_pago_id": ids["medio_id"], "monto": "50.00",
            "idempotency_key": "pago-add-0002",
        },
    )
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/items",
        headers=admin,
        json={"items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}]},
    )
    assert r.status_code == 409, r.text
    assert "otra orden" in r.json()["detail"]


def test_quitar_una_linea_vieja_exige_firma_y_una_reciente_no(env):
    """Los dos tramos de RN-COM-029 sobre la línea, no sobre la orden."""
    from datetime import timedelta

    from sqlalchemy import update

    from src.modules.sales.infrastructure.models import VentaItem

    client, ids, TestSession = env
    cajero = _token(client, "cajero_test", "111111")
    venta = client.post(
        "/api/v1/sales/ventas",
        headers=cajero,
        json={
            "sucursal_id": ids["sucursal_id"], "punto_venta_id": ids["pv_id"],
            "canal": "pdv", "modalidad": "takeout", "idempotency_key": "qui-0001",
            "items": [
                {"producto_comercial_id": ids["producto_id"], "cantidad": "1"},
                {"producto_comercial_id": ids["producto_id"], "cantidad": "1",
                 "grupo_cobro": 2},
            ],
        },
    ).json()
    lineas = client.get(
        f"/api/v1/sales/ventas/{venta['id']}/items", headers=cajero
    ).json()
    reciente, vieja = lineas[0]["id"], lineas[1]["id"]

    # La recién enviada la quita el cajero solo.
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/anular-lineas",
        headers=cajero,
        json={"venta_item_ids": [reciente], "motivo": "Se equivocó de mesa"},
    )
    assert r.status_code == 200, r.text

    with TestSession() as s:
        s.execute(
            update(VentaItem)
            .where(VentaItem.id == uuid.UUID(vieja))
            .values(created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=30))
        )
        s.commit()

    sin_firma = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/anular-lineas",
        headers=cajero,
        json={"venta_item_ids": [vieja], "motivo": "El cliente se arrepintió"},
    )
    assert sin_firma.status_code == 403, sin_firma.text
    assert "supervisor" in sin_firma.json()["detail"]

    con_firma = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/anular-lineas",
        headers=cajero,
        json={
            "venta_item_ids": [vieja],
            "motivo": "El cliente se arrepintió",
            "autorizacion": _autorizacion(client, "sales.anular"),
        },
    )
    assert con_firma.status_code == 200, con_firma.text
    assert con_firma.json()["estado"] == "anulada"
