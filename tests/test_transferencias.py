"""Tests del ciclo de abastecimiento interno (ADR-020): reserva de stock,
solicitud de insumos y transferencia con recepción. SQLite en memoria +
override de get_db, igual que `test_inventory.py`.
"""

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
        marca = s.scalar(select(Marca))
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        central = Almacen(empresa_id=empresa.id, nombre="Central", tipo="central")
        s.add_all([udm, central])
        s.flush()
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        s.add(sucursal)
        s.flush()
        # El almacén de local declara de quién se abastece: la solicitud no
        # tiene que decirlo en cada request.
        local = Almacen(
            empresa_id=empresa.id, sucursal_id=sucursal.id, nombre="Local Centro",
            tipo="sucursal", almacen_abastecedor_id=central.id,
        )
        otro_local = Almacen(
            empresa_id=empresa.id, sucursal_id=sucursal.id, nombre="Local Norte",
            tipo="sucursal", almacen_abastecedor_id=central.id,
        )
        s.add_all([local, otro_local])
        s.flush()
        # Perecible (mueve por lote y FEFO) y no perecible.
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
        almacenero = Usuario(
            username="almacenero1", pin_hash=hash_pin("654321"), tipo="humano",
        )
        s.add(almacenero)
        s.flush()
        rol_alm = s.scalar(select(Rol).where(Rol.nombre == "almacenero"))
        s.add_all([
            UsuarioRol(usuario_id=almacenero.id, rol_id=rol_alm.id),
            UsuarioSucursal(usuario_id=almacenero.id, sucursal_id=sucursal.id),
        ])
        ids.update(
            empresa_id=str(empresa.id), central_id=str(central.id),
            local_id=str(local.id), otro_local_id=str(otro_local.id),
            queso_id=str(queso.id), sku_queso=str(sku_q.id),
            sku_servilleta=str(sku_s.id),
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


def _ingresar(client, h, almacen_id, sku, cantidad, lote_id=None):
    body = {
        "almacen_id": almacen_id, "sku_id": sku,
        "cantidad": str(cantidad), "tipo": "recepcion_compra",
    }
    if lote_id:
        body["lote_id"] = lote_id
    r = client.post("/api/v1/inventory/movimientos", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _crear_lote(client, h, ids, codigo, vencimiento):
    r = client.post("/api/v1/inventory/lotes", headers=h, json={
        "articulo_id": ids["queso_id"], "codigo": codigo,
        "fecha_vencimiento": vencimiento, "origen": "compra",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _stock(client, h, almacen_id, sku):
    filas = client.get(
        f"/api/v1/inventory/stock?almacen_id={almacen_id}", headers=h).json()["items"]
    return next((f for f in filas if f["sku_id"] == sku), None)


def _solicitar(client, h, ids, items=None, almacen_solicitante_id=None):
    return client.post("/api/v1/inventory/solicitudes", headers=h, json={
        "almacen_solicitante_id": almacen_solicitante_id or ids["local_id"],
        "items": items or [{"sku_id": ids["sku_servilleta"], "cantidad": "10"}],
    })


def _ciclo_hasta_aprobada(client, ids, cantidad="10", sku=None):
    """Solicita como almacenero y aprueba como admin (aprobador ≠ solicitante)."""
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)
    sol = _solicitar(client, h_alm, ids, [
        {"sku_id": sku or ids["sku_servilleta"], "cantidad": cantidad},
    ]).json()
    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/aprobar",
        headers=h_admin, json={},
    )
    assert r.status_code == 200, r.text
    return sol, h_alm, h_admin


# --- Reserva de stock -------------------------------------------------------
def test_aprobar_reserva_y_baja_el_disponible(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)

    _ciclo_hasta_aprobada(client, ids, "30")

    fila = _stock(client, h, ids["central_id"], ids["sku_servilleta"])
    # El físico no se movió: la reserva es una promesa, no una salida.
    assert Decimal(fila["cantidad"]) == Decimal("100")
    assert Decimal(fila["reservado"]) == Decimal("30")
    assert Decimal(fila["disponible"]) == Decimal("70")


def test_no_se_reserva_mas_que_el_disponible(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 50)
    _ciclo_hasta_aprobada(client, ids, "40")

    # Quedan 10 disponibles aunque el físico siga en 50.
    h_alm = _token(client, "almacenero1", "654321")
    sol = _solicitar(client, h_alm, ids, [
        {"sku_id": ids["sku_servilleta"], "cantidad": "20"},
    ]).json()
    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/aprobar", headers=h, json={})
    assert r.status_code == 409
    assert "disponible insuficiente" in r.json()["detail"]


def test_cancelar_libera_la_reserva(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    sol, h_alm, _ = _ciclo_hasta_aprobada(client, ids, "30")

    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/cancelar", headers=h_alm)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelada"

    fila = _stock(client, h, ids["central_id"], ids["sku_servilleta"])
    assert Decimal(fila["disponible"]) == Decimal("100")
    assert client.get("/api/v1/inventory/reservas", headers=h).json() == []


def test_liberacion_manual_de_reserva(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    _ciclo_hasta_aprobada(client, ids, "30")

    reserva = client.get("/api/v1/inventory/reservas", headers=h).json()[0]
    r = client.post(
        f"/api/v1/inventory/reservas/{reserva['id']}/liberar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "liberada"
    assert Decimal(
        _stock(client, h, ids["central_id"], ids["sku_servilleta"])["disponible"]
    ) == Decimal("100")
    # Soltarla dos veces no tiene sentido.
    assert client.post(
        f"/api/v1/inventory/reservas/{reserva['id']}/liberar", headers=h
    ).status_code == 409


def test_una_venta_no_se_bloquea_por_una_reserva(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 50)
    _ciclo_hasta_aprobada(client, ids, "50")  # todo reservado

    # El consumo ya ocurrió en el mundo real: el ERP lo registra igual y el
    # disponible queda negativo, que es la señal de la promesa sin respaldo.
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["central_id"], "sku_id": ids["sku_servilleta"],
        "cantidad": "-20", "tipo": "consumo_venta",
    })
    assert r.status_code == 201, r.text
    fila = _stock(client, h, ids["central_id"], ids["sku_servilleta"])
    assert Decimal(fila["cantidad"]) == Decimal("30")
    assert Decimal(fila["disponible"]) == Decimal("-20")


# --- Solicitud de insumos ---------------------------------------------------
def test_abastecedor_se_toma_del_almacen(env):
    client, ids, _ = env
    h = _token(client, "almacenero1", "654321")
    r = _solicitar(client, h, ids)
    assert r.status_code == 201, r.text
    assert r.json()["almacen_abastecedor_id"] == ids["central_id"]


def test_almacen_sin_abastecedor_exige_indicarlo(env):
    client, ids, _ = env
    h = _token(client, "almacenero1", "654321")
    # El central no tiene abastecedor configurado.
    r = _solicitar(client, h, ids, almacen_solicitante_id=ids["central_id"])
    assert r.status_code == 409
    assert "no tiene abastecedor configurado" in r.json()["detail"]


def test_quien_solicita_no_aprueba(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    # El admin solicita y el admin intenta aprobar.
    sol = _solicitar(client, h, ids).json()
    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/aprobar", headers=h, json={})
    assert r.status_code == 409
    assert "no puede ser quien solicitó" in r.json()["detail"]


def test_no_se_aprueba_mas_de_lo_solicitado(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    h_alm = _token(client, "almacenero1", "654321")
    sol = _solicitar(client, h_alm, ids, [
        {"sku_id": ids["sku_servilleta"], "cantidad": "10"},
    ]).json()
    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/aprobar", headers=h,
        json={"aprobadas": [{"sku_id": ids["sku_servilleta"], "cantidad": "15"}]},
    )
    assert r.status_code == 409
    assert "no se aprueba más de lo solicitado" in r.json()["detail"]


def test_aprobacion_recortada_reserva_solo_lo_aprobado(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    h_alm = _token(client, "almacenero1", "654321")
    sol = _solicitar(client, h_alm, ids, [
        {"sku_id": ids["sku_servilleta"], "cantidad": "40"},
    ]).json()
    client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/aprobar", headers=h,
        json={"aprobadas": [{"sku_id": ids["sku_servilleta"], "cantidad": "25"}]},
    )
    detalle = client.get(
        f"/api/v1/inventory/solicitudes/{sol['id']}", headers=h).json()
    assert Decimal(detalle["items"][0]["cantidad_solicitada"]) == Decimal("40")
    assert Decimal(detalle["items"][0]["cantidad_aprobada"]) == Decimal("25")
    assert Decimal(
        _stock(client, h, ids["central_id"], ids["sku_servilleta"])["reservado"]
    ) == Decimal("25")


def test_rechazar_no_reserva_nada(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    h_alm = _token(client, "almacenero1", "654321")
    sol = _solicitar(client, h_alm, ids).json()
    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/rechazar", headers=h)
    assert r.json()["estado"] == "rechazada"
    assert client.get("/api/v1/inventory/reservas", headers=h).json() == []


def test_solicitar_exige_permiso(env):
    client, ids, _ = env
    h = _token(client, "almacenero1", "654321")
    # El almacenero solicita pero no aprueba.
    sol = _solicitar(client, h, ids).json()
    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol['id']}/aprobar", headers=h, json={})
    assert r.status_code == 403


# --- Despacho y recepción ---------------------------------------------------
def test_ciclo_completo_descuenta_origen_y_suma_destino(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    sol, _, h_admin = _ciclo_hasta_aprobada(client, ids, "30")

    r = client.post("/api/v1/inventory/transferencias", headers=h_admin, json={
        "origen_almacen_id": ids["central_id"],
        "destino_almacen_id": ids["local_id"],
        "solicitud_id": sol["id"],
    })
    assert r.status_code == 201, r.text
    transferencia = r.json()
    assert transferencia["estado"] == "en_transito"

    # En tránsito: salió del origen y todavía no entró al destino.
    origen = _stock(client, h, ids["central_id"], ids["sku_servilleta"])
    assert Decimal(origen["cantidad"]) == Decimal("70")
    # La reserva se consumió: no puede seguir descontando el disponible.
    assert Decimal(origen["reservado"]) == Decimal("0")
    assert Decimal(origen["disponible"]) == Decimal("70")
    assert _stock(client, h, ids["local_id"], ids["sku_servilleta"]) is None
    assert client.get(
        f"/api/v1/inventory/solicitudes/{sol['id']}", headers=h
    ).json()["estado"] == "despachada"

    r = client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin, json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "recibida"
    destino = _stock(client, h, ids["local_id"], ids["sku_servilleta"])
    assert Decimal(destino["cantidad"]) == Decimal("30")
    assert client.get(
        f"/api/v1/inventory/solicitudes/{sol['id']}", headers=h
    ).json()["estado"] == "recibida"


def test_no_se_despacha_mas_de_lo_aprobado(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    sol, _, h_admin = _ciclo_hasta_aprobada(client, ids, "30")

    r = client.post("/api/v1/inventory/transferencias", headers=h_admin, json={
        "origen_almacen_id": ids["central_id"],
        "destino_almacen_id": ids["local_id"],
        "solicitud_id": sol["id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "31"}],
    })
    assert r.status_code == 409
    assert "no se despacha más de lo aprobado" in r.json()["detail"]


def test_despacho_parcial_deja_la_diferencia_a_la_vista(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    sol, _, h_admin = _ciclo_hasta_aprobada(client, ids, "30")

    # El central solo tenía 20 en el estante: despacha lo que hay.
    r = client.post("/api/v1/inventory/transferencias", headers=h_admin, json={
        "origen_almacen_id": ids["central_id"],
        "destino_almacen_id": ids["local_id"],
        "solicitud_id": sol["id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "20"}],
    })
    assert r.status_code == 201, r.text
    item = client.get(
        f"/api/v1/inventory/solicitudes/{sol['id']}", headers=h).json()["items"][0]
    assert Decimal(item["cantidad_aprobada"]) == Decimal("30")
    assert Decimal(item["cantidad_despachada"]) == Decimal("20")


def test_recepcion_con_faltante_queda_auditable(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    sol, _, h_admin = _ciclo_hasta_aprobada(client, ids, "30")
    transferencia = client.post(
        "/api/v1/inventory/transferencias", headers=h_admin, json={
            "origen_almacen_id": ids["central_id"],
            "destino_almacen_id": ids["local_id"],
            "solicitud_id": sol["id"],
        }).json()
    item_id = client.get(
        f"/api/v1/inventory/transferencias/{transferencia['id']}", headers=h
    ).json()["items"][0]["id"]

    eventos = []
    event_bus.subscribe("inventory.transferencia_recibida", eventos.append)
    r = client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin, json={"items": [{"item_id": item_id, "cantidad": "28"}]},
    )
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert Decimal(item["cantidad_enviada"]) == Decimal("30")
    assert Decimal(item["cantidad_recibida"]) == Decimal("28")
    assert Decimal(item["diferencia"]) == Decimal("-2")
    # Entra al stock lo que de verdad llegó, no lo que decía el papel.
    assert Decimal(
        _stock(client, h, ids["local_id"], ids["sku_servilleta"])["cantidad"]
    ) == Decimal("28")
    assert eventos[-1]["diferencias"][0]["recibida"] == "28"


def test_no_se_recibe_mas_de_lo_enviado(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    sol, _, h_admin = _ciclo_hasta_aprobada(client, ids, "30")
    transferencia = client.post(
        "/api/v1/inventory/transferencias", headers=h_admin, json={
            "origen_almacen_id": ids["central_id"],
            "destino_almacen_id": ids["local_id"],
            "solicitud_id": sol["id"],
        }).json()
    item_id = client.get(
        f"/api/v1/inventory/transferencias/{transferencia['id']}", headers=h
    ).json()["items"][0]["id"]

    r = client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin, json={"items": [{"item_id": item_id, "cantidad": "35"}]},
    )
    assert r.status_code == 409
    assert "no se recibe más de lo enviado" in r.json()["detail"]


def test_no_se_recibe_dos_veces(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    sol, _, h_admin = _ciclo_hasta_aprobada(client, ids, "30")
    transferencia = client.post(
        "/api/v1/inventory/transferencias", headers=h_admin, json={
            "origen_almacen_id": ids["central_id"],
            "destino_almacen_id": ids["local_id"],
            "solicitud_id": sol["id"],
        }).json()
    ruta = f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir"
    assert client.post(ruta, headers=h_admin, json={}).status_code == 200
    assert client.post(ruta, headers=h_admin, json={}).status_code == 409


# --- FEFO en la transferencia -----------------------------------------------
def test_el_despacho_reparte_por_fefo_y_el_destino_recibe_esos_lotes(env):
    client, ids, _ = env
    h = _token(client)
    lejano = _crear_lote(client, h, ids, "L-LEJANO", "2027-12-31")
    cercano = _crear_lote(client, h, ids, "L-CERCANO", "2026-12-31")
    _ingresar(client, h, ids["central_id"], ids["sku_queso"], 6, lejano)
    _ingresar(client, h, ids["central_id"], ids["sku_queso"], 4, cercano)

    sol, _, h_admin = _ciclo_hasta_aprobada(client, ids, "6", sku=ids["sku_queso"])
    transferencia = client.post(
        "/api/v1/inventory/transferencias", headers=h_admin, json={
            "origen_almacen_id": ids["central_id"],
            "destino_almacen_id": ids["local_id"],
            "solicitud_id": sol["id"],
        }).json()

    items = client.get(
        f"/api/v1/inventory/transferencias/{transferencia['id']}", headers=h
    ).json()["items"]
    # 6 kg salen de dos lotes: primero el que vence antes (4) y luego 2 del otro.
    por_lote = {i["lote_id"]: Decimal(i["cantidad_enviada"]) for i in items}
    assert por_lote == {cercano: Decimal("4"), lejano: Decimal("2")}

    client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin, json={},
    )
    destino = {
        x["codigo"]: Decimal(x["cantidad"])
        for x in client.get(
            f"/api/v1/inventory/lotes?almacen_id={ids['local_id']}", headers=h
        ).json()
    }
    assert destino == {"L-CERCANO": Decimal("4"), "L-LEJANO": Decimal("2")}


# --- Transferencia lateral --------------------------------------------------
def test_transferencia_lateral_sin_solicitud(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 40)

    r = client.post("/api/v1/inventory/transferencias", headers=h, json={
        "origen_almacen_id": ids["local_id"],
        "destino_almacen_id": ids["otro_local_id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "15"}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["solicitud_id"] is None

    client.post(
        f"/api/v1/inventory/transferencias/{r.json()['id']}/recibir",
        headers=h, json={},
    )
    assert Decimal(
        _stock(client, h, ids["local_id"], ids["sku_servilleta"])["cantidad"]
    ) == Decimal("25")
    assert Decimal(
        _stock(client, h, ids["otro_local_id"], ids["sku_servilleta"])["cantidad"]
    ) == Decimal("15")


def test_transferencia_lateral_exige_items(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/transferencias", headers=h, json={
        "origen_almacen_id": ids["local_id"],
        "destino_almacen_id": ids["otro_local_id"],
    })
    assert r.status_code == 409
    assert "ítems explícitos" in r.json()["detail"]


def test_origen_y_destino_distintos(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/transferencias", headers=h, json={
        "origen_almacen_id": ids["local_id"],
        "destino_almacen_id": ids["local_id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "1"}],
    })
    assert r.status_code == 409


def test_despachar_sin_stock_falla_entera(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/inventory/transferencias", headers=h, json={
        "origen_almacen_id": ids["local_id"],
        "destino_almacen_id": ids["otro_local_id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "5"}],
    })
    assert r.status_code == 409
    assert "insuficiente" in r.json()["detail"]
    assert client.get(
        f"/api/v1/inventory/transferencias?almacen_id={ids['local_id']}", headers=h
    ).json()["items"] == []
