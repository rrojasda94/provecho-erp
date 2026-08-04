"""Tests del conteo cíclico (ADR-019): programa derivado por frecuencia de
categoría, conteo a ciegas, ajustes generados al cerrar y reporte de lo
que no se contó en su fecha. SQLite en memoria + override de get_db, igual
que `test_inventory.py`.
"""

import datetime
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
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Conteo,
    Sku,
    UnidadMedida,
)
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

HOY = fechas.hoy()


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        almacen = Almacen(empresa_id=empresa.id, nombre="Central", tipo="central")
        # Perecible a diario, abarrote al mes: el punto del slice es que la
        # periodicidad la fija la categoría, no un número universal.
        perecibles = Categoria(
            empresa_id=empresa.id, nombre="Perecibles", frecuencia_conteo="diario"
        )
        abarrotes = Categoria(
            empresa_id=empresa.id, nombre="Abarrotes", frecuencia_conteo="mensual"
        )
        # Sin frecuencia: fuera del ciclo, nunca aparece en el programa.
        descartables = Categoria(empresa_id=empresa.id, nombre="Descartables")
        s.add_all([udm, almacen, perecibles, abarrotes, descartables])
        s.flush()
        queso = Articulo(
            empresa_id=empresa.id, id_interno="Q001", nombre="Queso",
            unidad_medida_id=udm.id, tipo="insumo", categoria_id=perecibles.id,
        )
        harina = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo", categoria_id=abarrotes.id,
        )
        s.add_all([queso, harina])
        s.flush()
        sku_q = Sku(articulo_id=queso.id, codigo="SKU-QUESO")
        sku_h = Sku(articulo_id=harina.id, codigo="SKU-HARINA")
        s.add_all([sku_q, sku_h])
        s.flush()
        # El almacenero cuenta pero no ve el stock esperado (a ciegas) ni
        # aprueba el ajuste que su conteo genera.
        marca = s.scalar(select(Marca))
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        almacenero = Usuario(
            username="almacenero1", pin_hash=hash_pin("654321"), tipo="humano",
        )
        s.add_all([sucursal, almacenero])
        s.flush()
        rol_alm = s.scalar(select(Rol).where(Rol.nombre == "almacenero"))
        s.add_all([
            UsuarioRol(usuario_id=almacenero.id, rol_id=rol_alm.id),
            UsuarioSucursal(usuario_id=almacenero.id, sucursal_id=sucursal.id),
        ])
        ids.update(
            empresa_id=str(empresa.id), almacen_id=str(almacen.id),
            perecibles_id=str(perecibles.id), abarrotes_id=str(abarrotes.id),
            descartables_id=str(descartables.id),
            sku_queso=str(sku_q.id), sku_harina=str(sku_h.id),
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


def _ingresar(client, h, ids, sku, cantidad):
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": sku,
        "cantidad": str(cantidad), "tipo": "recepcion_compra",
    })
    assert r.status_code == 201, r.text


def _abrir(client, h, ids, categoria_id=None, tipo="rutina"):
    body = {"almacen_id": ids["almacen_id"], "tipo": tipo}
    if categoria_id:
        body["categoria_id"] = categoria_id
    return client.post("/api/v1/inventory/conteos", headers=h, json=body)


def _atrasar_conteo(TestSession, conteo_id, dias):
    """Envejece el conteo cerrado para que el programa lo vea vencido sin
    tener que esperar días reales."""
    with TestSession() as s:
        conteo = s.get(Conteo, uuid.UUID(conteo_id))
        conteo.cerrado_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            days=dias
        )
        s.commit()


# --- Frecuencia por categoría -----------------------------------------------
def test_frecuencia_se_configura_en_la_categoria(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/categorias", headers=h, json={
        "empresa_id": ids["empresa_id"],
        "nombre": "Bebidas", "frecuencia_conteo": "semanal",
    })
    assert r.status_code == 201, r.text
    assert r.json()["frecuencia_conteo"] == "semanal"

    cat_id = r.json()["id"]
    r = client.patch(f"/api/v1/inventory/categorias/{cat_id}", headers=h, json={
        "frecuencia_conteo": "quincenal",
    })
    assert r.status_code == 200
    assert r.json()["frecuencia_conteo"] == "quincenal"

    # Sacarla del ciclo exige el flag explícito: mandar null no alcanza.
    r = client.patch(f"/api/v1/inventory/categorias/{cat_id}", headers=h, json={
        "frecuencia_conteo": None,
    })
    assert r.json()["frecuencia_conteo"] == "quincenal"
    r = client.patch(f"/api/v1/inventory/categorias/{cat_id}", headers=h, json={
        "quitar_frecuencia": True,
    })
    assert r.json()["frecuencia_conteo"] is None


def test_frecuencia_invalida_rechazada(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/categorias", headers=h, json={
        "empresa_id": ids["empresa_id"],
        "nombre": "Congelados", "frecuencia_conteo": "cada_luna_llena",
    })
    assert r.status_code == 409
    assert "frecuencia de conteo inválida" in r.json()["detail"]


# --- Programa derivado ------------------------------------------------------
def test_programa_solo_incluye_categorias_con_frecuencia(env):
    client, ids, _ = env
    h = _token(client)
    r = client.get("/api/v1/inventory/conteos/programa", headers=h)
    assert r.status_code == 200, r.text
    categorias = {f["categoria"] for f in r.json()}
    assert categorias == {"Perecibles", "Abarrotes"}
    assert "Descartables" not in categorias


def test_programa_ordena_lo_vencido_primero(env):
    client, ids, _ = env
    h = _token(client)
    # Nunca contadas: el reloj arranca en el alta de la categoría. Ambas
    # están al día recién creadas, pero la diaria vence mañana y la mensual
    # dentro de un mes.
    filas = {f["categoria"]: f for f in client.get(
        "/api/v1/inventory/conteos/programa", headers=h).json()}
    assert filas["Perecibles"]["frecuencia"] == "diario"
    assert filas["Perecibles"]["estado"] == "al_dia"
    assert filas["Perecibles"]["proxima_fecha"] == str(HOY + datetime.timedelta(days=1))
    assert filas["Abarrotes"]["proxima_fecha"] == str(HOY + datetime.timedelta(days=30))
    assert filas["Abarrotes"]["ultimo_conteo"] is None
    # El más próximo a vencer encabeza la lista (y el vencido, antes que él).
    assert client.get(
        "/api/v1/inventory/conteos/programa", headers=h
    ).json()[0]["categoria"] == "Perecibles"


def test_conteo_cerrado_reinicia_el_reloj(env):
    client, ids, TestSession = env
    h = _token(client)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    client.post(f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h)

    filas = {f["categoria"]: f for f in client.get(
        "/api/v1/inventory/conteos/programa", headers=h).json()}
    assert filas["Perecibles"]["ultimo_conteo"] == str(HOY)
    assert filas["Perecibles"]["estado"] == "al_dia"
    assert filas["Perecibles"]["dias_atraso"] == -1


def test_conteo_general_satisface_a_todas_las_categorias(env):
    client, ids, _ = env
    h = _token(client)
    general = _abrir(client, h, ids).json()  # sin categoria_id
    client.post(f"/api/v1/inventory/conteos/{general['id']}/cerrar", headers=h)

    filas = {f["categoria"]: f for f in client.get(
        "/api/v1/inventory/conteos/programa", headers=h).json()}
    assert filas["Perecibles"]["ultimo_conteo"] == str(HOY)
    assert filas["Abarrotes"]["ultimo_conteo"] == str(HOY)


# --- Reporte de vencidos ----------------------------------------------------
def test_conteo_vencido_reporta_a_almacen_y_gerencia(env):
    client, ids, TestSession = env
    h = _token(client)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    client.post(f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h)
    _atrasar_conteo(TestSession, conteo["id"], dias=4)

    recibidos = []
    event_bus.subscribe("inventory.conteo_vencido", recibidos.append)
    r = client.post("/api/v1/inventory/conteos/verificar-vencidos", headers=h)

    assert r.status_code == 200, r.text
    vencidos = r.json()
    assert [f["categoria"] for f in vencidos] == ["Perecibles"]
    assert vencidos[0]["dias_atraso"] == 3  # cerrado hace 4 días, frecuencia 1
    assert len(recibidos) == 1
    assert recibidos[0]["dirigido_a"] == ["almacen", "gerencia"]
    assert recibidos[0]["frecuencia"] == "diario"


def test_al_dia_no_genera_reporte(env):
    client, ids, _ = env
    h = _token(client)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    client.post(f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h)

    recibidos = []
    event_bus.subscribe("inventory.conteo_vencido", recibidos.append)
    r = client.post("/api/v1/inventory/conteos/verificar-vencidos", headers=h)
    assert r.json() == []
    assert recibidos == []


# --- Apertura y snapshot ----------------------------------------------------
def test_abrir_conteo_congela_el_stock_de_la_categoria(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids, ids["sku_queso"], 10)
    _ingresar(client, h, ids, ids["sku_harina"], 25)

    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    detalle = client.get(
        f"/api/v1/inventory/conteos/{conteo['id']}", headers=h).json()
    # Solo el SKU de la categoría contada.
    assert [i["sku_id"] for i in detalle["items"]] == [ids["sku_queso"]]
    assert Decimal(detalle["items"][0]["cantidad_sistema"]) == Decimal("10")

    # Un movimiento posterior no altera lo congelado: la base es el momento
    # de abrir, no el de cerrar.
    _ingresar(client, h, ids, ids["sku_queso"], 5)
    detalle = client.get(
        f"/api/v1/inventory/conteos/{conteo['id']}", headers=h).json()
    assert Decimal(detalle["items"][0]["cantidad_sistema"]) == Decimal("10")


def test_no_se_abren_dos_conteos_sobre_la_misma_categoria(env):
    client, ids, _ = env
    h = _token(client)
    assert _abrir(client, h, ids, ids["perecibles_id"]).status_code == 201
    r = _abrir(client, h, ids, ids["perecibles_id"])
    assert r.status_code == 409
    # Otra categoría sí puede contarse en paralelo.
    assert _abrir(client, h, ids, ids["abarrotes_id"]).status_code == 201


def test_conteo_general_abierto_bloquea_el_de_categoria(env):
    client, ids, _ = env
    h = _token(client)
    assert _abrir(client, h, ids).status_code == 201
    assert _abrir(client, h, ids, ids["perecibles_id"]).status_code == 409


def test_tipo_de_conteo_invalido_rechazado(env):
    client, ids, _ = env
    h = _token(client)
    r = _abrir(client, h, ids, ids["perecibles_id"], tipo="inopinado")
    assert r.status_code == 409
    assert "tipo de conteo inválido" in r.json()["detail"]


# --- Conteo a ciegas --------------------------------------------------------
def test_almacenero_cuenta_a_ciegas(env):
    client, ids, _ = env
    h_admin = _token(client)
    _ingresar(client, h_admin, ids, ids["sku_queso"], 10)
    conteo = _abrir(client, h_admin, ids, ids["perecibles_id"]).json()

    h_alm = _token(client, "almacenero1", "654321")
    detalle = client.get(
        f"/api/v1/inventory/conteos/{conteo['id']}", headers=h_alm).json()
    assert detalle["items"][0]["cantidad_sistema"] is None
    assert detalle["items"][0]["diferencia"] is None

    # El admin (permiso ver_stock_esperado) sí lo ve.
    detalle = client.get(
        f"/api/v1/inventory/conteos/{conteo['id']}", headers=h_admin).json()
    assert Decimal(detalle["items"][0]["cantidad_sistema"]) == Decimal("10")


# --- Registro y cierre ------------------------------------------------------
def test_cerrar_genera_ajuste_por_diferencia(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids, ids["sku_queso"], 10)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()

    r = client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cantidades", headers=h,
        json={"items": [{"sku_id": ids["sku_queso"], "cantidad": "7"}]},
    )
    assert r.status_code == 200, r.text

    r = client.post(f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h)
    assert r.status_code == 200, r.text
    cierre = r.json()
    assert cierre["conteo"]["estado"] == "cerrado"
    assert len(cierre["ajustes"]) == 1
    ajuste = cierre["ajustes"][0]
    assert Decimal(ajuste["cantidad"]) == Decimal("-3")
    assert ajuste["motivo"] == "faltante"
    assert ajuste["estado"] == "pendiente"
    assert ajuste["conteo_id"] == conteo["id"]
    # 3 sobre 10 es 30%: muy por fuera del 2% de margen.
    assert ajuste["dentro_margen"] is False

    # El conteo no movió stock: el ajuste sigue pendiente de aprobación.
    stock = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['almacen_id']}", headers=h).json()
    assert Decimal(next(
        s["cantidad"] for s in stock if s["sku_id"] == ids["sku_queso"])) == Decimal("10")


def test_diferencia_dentro_del_margen_no_alarma(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids, ids["sku_queso"], 1000)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cantidades", headers=h,
        json={"items": [{"sku_id": ids["sku_queso"], "cantidad": "990"}]},
    )
    ajustes = client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h).json()["ajustes"]
    assert ajustes[0]["dentro_margen"] is True  # 10 de 1000 = 1% ≤ 2%


def test_sin_diferencia_no_hay_ajuste(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids, ids["sku_queso"], 10)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cantidades", headers=h,
        json={"items": [{"sku_id": ids["sku_queso"], "cantidad": "10"}]},
    )
    r = client.post(f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h)
    assert r.json()["ajustes"] == []


def test_item_no_contado_no_genera_faltante(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids, ids["sku_queso"], 10)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    # Se cierra sin haber contado nada: un conteo parcial no puede declarar
    # faltante lo que nadie miró.
    r = client.post(f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h)
    assert r.json()["ajustes"] == []


def test_sku_fuera_del_snapshot_entra_como_sobrante(env):
    client, ids, _ = env
    h = _token(client)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    # El queso nunca tuvo stock en este almacén, pero apareció en el conteo.
    client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cantidades", headers=h,
        json={"items": [{"sku_id": ids["sku_queso"], "cantidad": "4"}]},
    )
    ajustes = client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h).json()["ajustes"]
    assert Decimal(ajustes[0]["cantidad"]) == Decimal("4")
    assert ajustes[0]["motivo"] == "sobrante"
    # Sistema en 0: no hay base para un porcentaje, así que exige mirarlo.
    assert ajustes[0]["dentro_margen"] is False


def test_no_se_registra_sobre_un_conteo_cerrado(env):
    client, ids, _ = env
    h = _token(client)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    client.post(f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h)
    r = client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cantidades", headers=h,
        json={"items": [{"sku_id": ids["sku_queso"], "cantidad": "1"}]},
    )
    assert r.status_code == 409
    assert client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h
    ).status_code == 409


def test_cantidad_negativa_rechazada(env):
    client, ids, _ = env
    h = _token(client)
    conteo = _abrir(client, h, ids, ids["perecibles_id"]).json()
    r = client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cantidades", headers=h,
        json={"items": [{"sku_id": ids["sku_queso"], "cantidad": "-1"}]},
    )
    assert r.status_code == 422


# --- Ajuste del conteo y segregación de funciones ---------------------------
def test_el_ajuste_del_conteo_lo_aprueba_otro_usuario(env):
    client, ids, _ = env
    h_admin = _token(client)
    _ingresar(client, h_admin, ids, ids["sku_queso"], 10)
    h_alm = _token(client, "almacenero1", "654321")
    conteo = _abrir(client, h_alm, ids, ids["perecibles_id"]).json()
    client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cantidades", headers=h_alm,
        json={"items": [{"sku_id": ids["sku_queso"], "cantidad": "8"}]},
    )
    ajuste = client.post(
        f"/api/v1/inventory/conteos/{conteo['id']}/cerrar", headers=h_alm
    ).json()["ajustes"][0]

    # Quien contó no puede aprobar su propio ajuste (RN-INV-006)...
    r = client.post(
        f"/api/v1/inventory/ajustes/{ajuste['id']}/aprobar", headers=h_alm)
    assert r.status_code == 403  # almacenero no tiene aprobar_ajuste

    r = client.post(
        f"/api/v1/inventory/ajustes/{ajuste['id']}/aprobar", headers=h_admin)
    assert r.status_code == 200, r.text
    stock = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['almacen_id']}", headers=h_admin
    ).json()
    assert Decimal(next(
        s["cantidad"] for s in stock if s["sku_id"] == ids["sku_queso"])) == Decimal("8")


def test_contar_exige_permiso(env):
    client, ids, _ = env
    h = _token(client, "almacenero1", "654321")
    # El almacenero cuenta...
    assert _abrir(client, h, ids, ids["perecibles_id"]).status_code == 201
    # ...pero no configura la frecuencia de la categoría.
    r = client.patch(
        f"/api/v1/inventory/categorias/{ids['perecibles_id']}", headers=h,
        json={"frecuencia_conteo": "semanal"},
    )
    assert r.status_code == 403
