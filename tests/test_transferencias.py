"""Tests del ciclo de abastecimiento interno (ADR-020): reserva de stock,
solicitud de insumos y transferencia con recepción. SQLite en memoria +
override de get_db, igual que `test_inventory.py`.
"""

import uuid
from datetime import UTC, datetime
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
from src.modules.users.api.deps import get_db, get_db_reportes
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

# Costo del insumo con el que se prueba el traslado: sin costo, el faltante
# valorizado siempre daría 0 y el test pasaría por vacío.
COSTO_SERVILLETA = Decimal("1.5000")


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
            costo_promedio=COSTO_SERVILLETA,
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
    app.dependency_overrides[get_db_reportes] = _override_get_db
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

    # Y alguien lo mira: hasta ahora el único modo de enterarse era consultar
    # el stock del SKU exacto, sabiendo de antemano cuál mirar.
    datos = client.post(
        "/api/v1/reportes/disponible_negativo/datos", headers=h, json={}
    )
    assert datos.status_code == 200, datos.text
    filas = datos.json()["filas"]
    assert len(filas) == 1
    assert filas[0]["articulo"] == "Servilleta"
    assert Decimal(filas[0]["disponible"]) == Decimal("-20")


def test_disponible_sano_no_aparece_en_el_reporte(env):
    client, ids, _ = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    _ciclo_hasta_aprobada(client, ids, "50")  # reservado, pero con respaldo

    datos = client.post(
        "/api/v1/reportes/disponible_negativo/datos", headers=h, json={}
    )
    assert datos.json()["filas"] == []


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
    # "vigente" y no "configurado": desde RN-INV-022 el mensaje cubre también
    # el caso de un principal configurado pero dado de baja, sin respaldo.
    assert "no tiene abastecedor vigente" in r.json()["detail"]


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
    # El faltante viaja **valorizado**: el costo es dato de inventory, y
    # `accounting` no puede ir a buscarlo sin importar su dominio.
    assert Decimal(eventos[-1]["monto_diferencia"]) == Decimal("2") * COSTO_SERVILLETA


def test_traslado_completo_no_deja_faltante_que_valorizar(env):
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

    eventos = []
    event_bus.subscribe("inventory.transferencia_recibida", eventos.append)
    r = client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin, json={"items": []},
    )
    assert r.status_code == 200, r.text
    assert eventos[-1]["diferencias"] == []
    assert Decimal(eventos[-1]["monto_diferencia"]) == 0


def test_recepcion_parcial_deja_el_resto_en_transito(env):
    """El camión que trae la mitad hoy: lo que llegó entra al stock, lo que
    falta sigue viajando y la transferencia no se cierra."""
    client, ids, _ = env
    h = _token(client)
    h_admin = h
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    _ingresar(client, h, ids["central_id"], ids["sku_queso"], 50)
    # Lateral con dos líneas: una llega hoy y la otra queda en la carretera.
    transferencia = client.post(
        "/api/v1/inventory/transferencias", headers=h_admin, json={
            "origen_almacen_id": ids["central_id"],
            "destino_almacen_id": ids["local_id"],
            "items": [
                {"sku_id": ids["sku_servilleta"], "cantidad": "20"},
                {"sku_id": ids["sku_queso"], "cantidad": "10"},
            ],
        }).json()
    detalle = client.get(
        f"/api/v1/inventory/transferencias/{transferencia['id']}", headers=h
    ).json()
    item_id = next(
        i["id"] for i in detalle["items"] if i["sku_id"] == ids["sku_servilleta"]
    )

    eventos = []
    event_bus.subscribe("inventory.transferencia_recibida", eventos.append)

    # Una parcial sin decir qué llegó no tiene sentido.
    assert client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin, json={"items": [], "parcial": True},
    ).status_code == 409

    r = client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin,
        json={"items": [{"item_id": item_id, "cantidad": "20"}], "parcial": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_transito"  # sigue abierta
    # Nadie avisa todavía: el evento vale una sola vez, al cerrar.
    assert eventos == []
    assert Decimal(
        _stock(client, h, ids["local_id"], ids["sku_servilleta"])["cantidad"]
    ) == Decimal("20")

    # La segunda entrega la cierra... y el ítem ya recibido no se recibe otra vez.
    assert client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin,
        json={"items": [{"item_id": item_id, "cantidad": "5"}], "parcial": True},
    ).status_code == 409

    r = client.post(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/recibir",
        headers=h_admin, json={"items": []},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "recibida"
    assert len(eventos) == 1


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


def test_el_respaldo_atiende_cuando_el_principal_esta_de_baja(env):
    """El respaldo existe para el día en que el central no está (RN-INV-022).

    Antes, dar de baja el abastecedor dejaba a la sucursal sin poder pedir
    nada y con un "almacén abastecedor no encontrado" que no le decía a nadie
    qué hacer.
    """
    client, ids, TestSession = env
    with TestSession() as s:
        segundo = Almacen(
            empresa_id=uuid.UUID(ids["empresa_id"]),
            nombre="Central Norte",
            tipo="central",
        )
        s.add(segundo)
        s.flush()
        local = s.get(Almacen, uuid.UUID(ids["local_id"]))
        local.almacen_abastecedor_respaldo_id = segundo.id
        s.commit()
        respaldo_id = str(segundo.id)

    h = _token(client, "almacenero1", "654321")
    # Con el principal vigente manda el principal: el respaldo no se usa
    # "por si acaso", se usa cuando hace falta.
    assert _solicitar(client, h, ids).json()["almacen_abastecedor_id"] == ids["central_id"]

    with TestSession() as s:
        s.get(Almacen, uuid.UUID(ids["central_id"])).deleted_at = datetime.now(UTC)
        s.commit()

    r = _solicitar(client, h, ids)
    assert r.status_code == 201, r.text
    assert r.json()["almacen_abastecedor_id"] == respaldo_id


def test_el_abastecedor_pedido_a_mano_no_cae_al_respaldo(env):
    """Quien nombra un almacén está pidiendo a ESE. Darle otro en silencio
    sería despachar desde donde no se pidió."""
    client, ids, TestSession = env
    with TestSession() as s:
        segundo = Almacen(
            empresa_id=uuid.UUID(ids["empresa_id"]),
            nombre="Central Norte",
            tipo="central",
        )
        s.add(segundo)
        s.flush()
        local = s.get(Almacen, uuid.UUID(ids["local_id"]))
        local.almacen_abastecedor_respaldo_id = segundo.id
        s.get(Almacen, uuid.UUID(ids["central_id"])).deleted_at = datetime.now(UTC)
        s.commit()

    h = _token(client, "almacenero1", "654321")
    r = client.post("/api/v1/inventory/solicitudes", headers=h, json={
        "almacen_solicitante_id": ids["local_id"],
        "almacen_abastecedor_id": ids["central_id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "10"}],
    })
    # 404 y no un 201 despachado desde el respaldo. El mensaje lo da el
    # scope del router, que rechaza el almacén dado de baja antes de llegar
    # al caso de uso; lo que importa acá es que **no hay fallback**.
    assert r.status_code == 404, r.text
    assert "no encontrado" in r.json()["detail"]


def test_el_circuito_completo_de_abastecimiento_interno(env):
    """Declarar → cargar → pedir → aprobar → despachar → recibir.

    El recorrido que el usuario no podía hacer y ningún test cubría entero.
    Cada paso estaba probado por separado y el circuito igual estaba roto:
    faltaba la primitiva del arranque (sin filas de `stock` la solicitud ni
    se aprueba, porque reservar exige disponible > 0) y faltaba la bandeja
    del abastecedor para encontrar qué despachar.
    """
    client, ids, _ = env
    h_admin = _token(client)
    h_alm = _token(client, "almacenero1", "654321")

    # 1. El central declara qué maneja y con cuánto arranca. Sin segundo
    #    usuario: es carga inicial, no un ajuste.
    declarar = client.post(
        f"/api/v1/inventory/almacenes/{ids['central_id']}/articulos",
        headers=h_alm,
        json={"articulos": [
            {"sku_id": ids["sku_servilleta"], "cantidad_inicial": "100"},
        ]},
    )
    assert declarar.status_code == 201
    assert Decimal(declarar.json()[0]["cantidad"]) == Decimal("100")

    # 2. El local pide.
    solicitud = client.post("/api/v1/inventory/solicitudes", headers=h_alm, json={
        "almacen_solicitante_id": ids["local_id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "30"}],
    }).json()
    client.post(
        f"/api/v1/inventory/solicitudes/{solicitud['id']}/enviar", headers=h_alm
    )

    # 3. El central la ve en SU bandeja — antes no había forma de preguntar
    #    "qué me piden", solo "qué pedí".
    bandeja = client.get(
        f"/api/v1/inventory/solicitudes?almacen_abastecedor_id={ids['central_id']}",
        headers=h_admin,
    ).json()
    assert [s["id"] for s in bandeja["items"]] == [solicitud["id"]]

    # 4. Aprobar (reserva) y despachar (mueve el stock).
    aprobar = client.post(
        f"/api/v1/inventory/solicitudes/{solicitud['id']}/aprobar",
        headers=h_admin, json={"aprobadas": []},
    )
    assert aprobar.status_code == 200

    transferencia = client.post("/api/v1/inventory/transferencias", headers=h_alm, json={
        "origen_almacen_id": ids["central_id"],
        "destino_almacen_id": ids["local_id"],
        "solicitud_id": solicitud["id"],
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "30"}],
    })
    assert transferencia.status_code == 201
    assert transferencia.json()["estado"] == "en_transito"

    # Salió del central y todavía no está en el local.
    assert _cantidad(client, h_admin, ids["central_id"], ids["sku_servilleta"]) == Decimal("70")
    assert _cantidad(client, h_admin, ids["local_id"], ids["sku_servilleta"]) is None

    # 5. El local recibe: recién ahí entra.
    recibir = client.post(
        f"/api/v1/inventory/transferencias/{transferencia.json()['id']}/recibir",
        headers=h_alm, json={"items": [], "parcial": False},
    )
    assert recibir.status_code == 200
    assert _cantidad(client, h_admin, ids["local_id"], ids["sku_servilleta"]) == Decimal("30")

    detalle = client.get(
        f"/api/v1/inventory/solicitudes/{solicitud['id']}", headers=h_admin
    ).json()
    assert detalle["estado"] == "recibida"


def _cantidad(client, h, almacen_id, sku_id):
    """El saldo de un SKU en un almacén, o `None` si ni siquiera tiene fila."""
    filas = client.get(
        f"/api/v1/inventory/stock?almacen_id={almacen_id}&sku_id={sku_id}",
        headers=h,
    ).json()["items"]
    return Decimal(filas[0]["cantidad"]) if filas else None
