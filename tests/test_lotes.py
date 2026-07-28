"""Tests de lote/FEFO (ADR-015): reparto por vencimiento, bloqueo de
vencidos y convivencia con los artículos que no controlan lote.
SQLite en memoria + override de get_db, igual que `test_inventory.py`.
"""

from datetime import date, timedelta
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
    CategoriaUdm,
    MovimientoInventario,
    Sku,
    UnidadMedida,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa

HOY = date.today()


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
        s.add_all([udm, almacen])
        s.flush()
        # Perecible (controla lote) y no perecible, para probar ambos caminos.
        queso = Articulo(
            empresa_id=empresa.id, id_interno="Q001", nombre="Queso",
            unidad_medida_id=udm.id, tipo="insumo", controla_lote=True,
        )
        servilleta = Articulo(
            empresa_id=empresa.id, id_interno="S001", nombre="Servilleta",
            unidad_medida_id=udm.id, tipo="suministro",
        )
        s.add_all([queso, servilleta])
        s.flush()
        sku_q = Sku(articulo_id=queso.id, codigo="SKU-QUESO")
        sku_s = Sku(articulo_id=servilleta.id, codigo="SKU-SERV")
        s.add_all([sku_q, sku_s])
        s.flush()
        ids.update(
            empresa_id=str(empresa.id), almacen_id=str(almacen.id),
            queso_id=str(queso.id), sku_queso=str(sku_q.id),
            servilleta_id=str(servilleta.id), sku_servilleta=str(sku_s.id),
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


def _crear_lote(client, h, ids, codigo, dias_a_vencer):
    r = client.post("/api/v1/inventory/lotes", headers=h, json={
        "articulo_id": ids["queso_id"],
        "codigo": codigo,
        "fecha_vencimiento": str(HOY + timedelta(days=dias_a_vencer)),
        "origen": "compra",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ingresar(client, h, ids, lote_id, cantidad, sku=None):
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": sku or ids["sku_queso"],
        "cantidad": str(cantidad), "tipo": "recepcion_compra", "lote_id": lote_id,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _salir(client, h, ids, cantidad, sku=None, lote_id=None):
    body = {
        "almacen_id": ids["almacen_id"], "sku_id": sku or ids["sku_queso"],
        "cantidad": str(-cantidad), "tipo": "consumo_venta",
    }
    if lote_id:
        body["lote_id"] = lote_id
    return client.post("/api/v1/inventory/movimientos", headers=h, json=body)


def test_fefo_consume_primero_el_que_vence_antes(env):
    client, ids, _ = env
    h = _token(client)
    lejano = _crear_lote(client, h, ids, "L-LEJANO", 30)
    cercano = _crear_lote(client, h, ids, "L-CERCANO", 3)
    _ingresar(client, h, ids, lejano, 10)   # ingresa primero el que vence después
    _ingresar(client, h, ids, cercano, 10)

    r = _salir(client, h, ids, 4)
    assert r.status_code == 201
    movs = r.json()
    assert len(movs) == 1
    assert movs[0]["lote_id"] == cercano  # FEFO, no FIFO de ingreso

    lotes = {x["codigo"]: x for x in client.get(
        "/api/v1/inventory/lotes", headers=h).json()}
    assert Decimal(lotes["L-CERCANO"]["cantidad"]) == Decimal("6")
    assert Decimal(lotes["L-LEJANO"]["cantidad"]) == Decimal("10")


def test_salida_se_reparte_entre_lotes(env):
    client, ids, _ = env
    h = _token(client)
    cercano = _crear_lote(client, h, ids, "L-CERCANO", 2)
    lejano = _crear_lote(client, h, ids, "L-LEJANO", 20)
    _ingresar(client, h, ids, cercano, 5)
    _ingresar(client, h, ids, lejano, 5)

    movs = _salir(client, h, ids, 8).json()
    assert len(movs) == 2  # un movimiento por lote tocado
    assert [m["lote_id"] for m in movs] == [cercano, lejano]
    assert [Decimal(m["cantidad"]) for m in movs] == [Decimal("-5"), Decimal("-3")]

    lotes = {x["codigo"]: x for x in client.get(
        "/api/v1/inventory/lotes", headers=h).json()}
    assert Decimal(lotes["L-CERCANO"]["cantidad"]) == 0
    assert lotes["L-CERCANO"]["estado"] == "agotado"
    assert Decimal(lotes["L-LEJANO"]["cantidad"]) == Decimal("2")


def test_lote_vencido_se_bloquea_y_publica_evento(env):
    client, ids, _ = env
    h = _token(client)
    recibidos = []
    event_bus.subscribe("inventory.lote_vencido_detectado", recibidos.append)

    vencido = _crear_lote(client, h, ids, "L-VENCIDO", -1)
    vigente = _crear_lote(client, h, ids, "L-VIGENTE", 10)
    _ingresar(client, h, ids, vencido, 6)
    _ingresar(client, h, ids, vigente, 6)

    movs = _salir(client, h, ids, 4).json()
    assert [m["lote_id"] for m in movs] == [vigente]  # el vencido no se despacha
    assert len(recibidos) == 1
    assert recibidos[0]["lote_id"] == vencido

    lotes = {x["codigo"]: x for x in client.get(
        "/api/v1/inventory/lotes", headers=h).json()}
    assert lotes["L-VENCIDO"]["estado"] == "bloqueado"
    assert lotes["L-VENCIDO"]["vencido"] is True
    assert Decimal(lotes["L-VENCIDO"]["cantidad"]) == Decimal("6")  # intacto


def test_barrido_bloquea_vencidos_sin_esperar_salida(env):
    client, ids, _ = env
    h = _token(client)
    vencido = _crear_lote(client, h, ids, "L-VENCIDO", -5)
    _ingresar(client, h, ids, vencido, 3)

    r = client.post("/api/v1/inventory/lotes/bloquear-vencidos", headers=h)
    assert r.status_code == 200
    assert [x["lote_id"] for x in r.json()] == [vencido]
    # Idempotente: el segundo barrido ya no encuentra nada disponible.
    assert client.post(
        "/api/v1/inventory/lotes/bloquear-vencidos", headers=h
    ).json() == []


def test_articulo_sin_control_de_lote_no_cambia(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_servilleta"],
        "cantidad": "100", "tipo": "recepcion_compra",
    })
    assert r.status_code == 201
    assert r.json()[0]["lote_id"] is None
    salida = _salir(client, h, ids, 30, sku=ids["sku_servilleta"])
    assert salida.status_code == 201
    assert len(salida.json()) == 1
    assert salida.json()[0]["lote_id"] is None
    assert client.get("/api/v1/inventory/lotes", headers=h).json() == []


def test_ingreso_sin_lote_de_articulo_con_lote_crea_el_del_dia(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_queso"],
        "cantidad": "7", "tipo": "recepcion_compra",
    })
    assert r.status_code == 201
    assert r.json()[0]["lote_id"] is not None  # nada entra fuera de la trazabilidad
    lotes = client.get("/api/v1/inventory/lotes", headers=h).json()
    assert len(lotes) == 1
    assert lotes[0]["fecha_vencimiento"] is None  # sin vencimiento declarado


def test_override_de_lote_explicito(env):
    client, ids, _ = env
    h = _token(client)
    cercano = _crear_lote(client, h, ids, "L-CERCANO", 1)
    lejano = _crear_lote(client, h, ids, "L-LEJANO", 40)
    _ingresar(client, h, ids, cercano, 5)
    _ingresar(client, h, ids, lejano, 5)

    movs = _salir(client, h, ids, 2, lote_id=lejano).json()
    assert [m["lote_id"] for m in movs] == [lejano]  # gana el override


def test_salida_mayor_que_stock_no_toca_lotes(env):
    client, ids, _ = env
    h = _token(client)
    lote = _crear_lote(client, h, ids, "L-UNICO", 10)
    _ingresar(client, h, ids, lote, 5)

    assert _salir(client, h, ids, 9).status_code == 409
    lotes = client.get("/api/v1/inventory/lotes", headers=h).json()
    assert Decimal(lotes[0]["cantidad"]) == Decimal("5")  # entera, sin consumo parcial


def test_por_vencer_dias_filtra(env):
    client, ids, _ = env
    h = _token(client)
    pronto = _crear_lote(client, h, ids, "L-PRONTO", 3)
    tarde = _crear_lote(client, h, ids, "L-TARDE", 90)
    _ingresar(client, h, ids, pronto, 1)
    _ingresar(client, h, ids, tarde, 1)

    r = client.get("/api/v1/inventory/lotes?por_vencer_dias=7", headers=h)
    assert [x["codigo"] for x in r.json()] == ["L-PRONTO"]


def test_lote_de_otro_articulo_rechazado(env):
    client, ids, _ = env
    h = _token(client)
    lote = _crear_lote(client, h, ids, "L-QUESO", 10)
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["almacen_id"], "sku_id": ids["sku_servilleta"],
        "cantidad": "5", "tipo": "recepcion_compra", "lote_id": lote,
    })
    assert r.status_code == 409


def test_movimientos_quedan_trazados_por_lote(env):
    client, ids, TestSession = env
    h = _token(client)
    cercano = _crear_lote(client, h, ids, "L-CERCANO", 2)
    lejano = _crear_lote(client, h, ids, "L-LEJANO", 30)
    _ingresar(client, h, ids, cercano, 4)
    _ingresar(client, h, ids, lejano, 4)
    _salir(client, h, ids, 6)

    with TestSession() as s:
        movs = list(s.scalars(select(MovimientoInventario)))
    assert len(movs) == 4  # 2 ingresos + 2 salidas (una por lote)
    assert all(m.lote_id is not None for m in movs)
