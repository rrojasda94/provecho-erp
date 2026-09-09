"""Tests de integración del slice core de `delivery` (ADR-098):
repartidores, tablero, rutas y entregas — con la cadena de eventos real
hacia y desde `sales` (delivery.entrega_registrada ⇄ sales.venta_entregada/
venta_anulada).
"""

import base64
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.delivery.application import listeners as delivery_listeners
from src.modules.delivery.application import repartidores as repartidores_uc
from src.modules.delivery.infrastructure.models import Entrega, RutaReparto
from src.modules.rrhh.infrastructure.models import Trabajador
from src.modules.sales.application import listeners as sales_listeners
from src.modules.sales.infrastructure.models import (
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Marca,
    Persona,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from tests.conftest import auth_headers

# Tarapoto — no importa si Google conoce el punto, solo que exista el ancla.
LAT_LOCAL = Decimal("-6.487000")
LNG_LOCAL = Decimal("-76.363000")
LAT_CLIENTE = Decimal("-6.490000")
LNG_CLIENTE = Decimal("-76.360000")


def _trabajador_con_cuenta(s, *, empresa, sucursal, nombres, username, rol_nombre):
    persona = Persona(nombres=nombres, apellidos="Test")
    s.add(persona)
    s.flush()
    usuario = Usuario(
        username=username,
        pin_hash=hash_pin("111111"),
        tipo="humano",
        persona_id=persona.id,
    )
    s.add(usuario)
    s.flush()
    rol = s.scalar(select(Rol).where(Rol.nombre == rol_nombre))
    s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
    trabajador = Trabajador(
        empresa_id=empresa.id,
        persona_id=persona.id,
        sucursal_id=sucursal.id,
        cargo="Repartidor",
        area="Operaciones",
        tipo_vinculo="planilla",
        fecha_ingreso=date(2026, 1, 1),
    )
    s.add(trabajador)
    s.flush()
    return usuario, trabajador


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(sales_listeners, "session_factory", TestSession)
    monkeypatch.setattr(delivery_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    headers = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        marca = s.scalar(select(Marca))
        sucursal = s.scalar(select(Sucursal).where(Sucursal.nombre == "CH1"))
        sucursal.ubicacion_lat = LAT_LOCAL
        sucursal.ubicacion_lng = LNG_LOCAL
        pv = PuntoVenta(
            sucursal_id=sucursal.id,
            canal="trabajador",
            serie_boleta="B001",
            serie_factura="F001",
            politica_pago="adelantado",
        )
        producto = ProductoComercial(id_interno="P001", marca_id=marca.id, nombre="Pizza")
        s.add_all([pv, producto])
        s.flush()

        usuario_rep1, trabajador1 = _trabajador_con_cuenta(
            s,
            empresa=empresa,
            sucursal=sucursal,
            nombres="Kevin",
            username="kevinrep",
            rol_nombre="repartidor",
        )
        _usuario_rep2, trabajador2 = _trabajador_con_cuenta(
            s,
            empresa=empresa,
            sucursal=sucursal,
            nombres="Ana",
            username="anarep",
            rol_nombre="repartidor",
        )
        s.flush()

        repartidor1 = repartidores_uc.crear(
            s,
            empresa_id=empresa.id,
            trabajador_id=trabajador1.id,
            sucursal_id=sucursal.id,
            vehiculo_tipo="moto",
        )
        repartidor2 = repartidores_uc.crear(
            s,
            empresa_id=empresa.id,
            trabajador_id=trabajador2.id,
            sucursal_id=sucursal.id,
            vehiculo_tipo="bicicleta",
        )
        s.flush()

        for username in ("aprobador1", "admin", "kevinrep", "anarep"):
            headers[username] = auth_headers(s, username)

        ids.update(
            empresa_id=str(empresa.id),
            sucursal_id=str(sucursal.id),
            producto_id=str(producto.id),
            trabajador1_id=str(trabajador1.id),
            trabajador2_id=str(trabajador2.id),
            repartidor1_id=str(repartidor1.id),
            repartidor2_id=str(repartidor2.id),
            usuario_rep1_id=str(usuario_rep1.id),
        )
        s.commit()

    app = _app_compartida

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c, ids, headers, TestSession


def _crear_venta_delivery(
    session, ids, *, estados_items=("listo",), con_ubicacion=True, estado="pagada"
):
    """Una venta delivery lista (o no) para entrar a una ruta."""
    venta = Venta(
        sucursal_id=uuid.UUID(ids["sucursal_id"]),
        numero_orden=int(uuid.uuid4().int % 100000),
        punto_venta_id=session.scalar(select(PuntoVenta.id)),
        canal="pdv",
        modalidad="delivery",
        usuario_id=session.scalar(select(Usuario.id).where(Usuario.username == "cajero1")),
        estado=estado,
        total=Decimal("35.00"),
        idempotency_key=str(uuid.uuid4()),
        direccion_entrega="Jr. Amazonas 123",
    )
    if con_ubicacion:
        venta.ubicacion_lat = LAT_CLIENTE
        venta.ubicacion_lng = LNG_CLIENTE
    session.add(venta)
    session.flush()
    for estado_item in estados_items:
        session.add(
            VentaItem(
                venta_id=venta.id,
                producto_comercial_id=uuid.UUID(ids["producto_id"]),
                cantidad=Decimal(1),
                precio_unitario=Decimal("35.00"),
                estado_preparacion=estado_item,
            )
        )
    session.flush()
    session.commit()
    return venta


# --- Repartidores ---------------------------------------------------------------
def test_candidatos_excluye_a_quien_ya_es_repartidor(env):
    client, ids, headers, _ = env
    r = client.get(
        "/api/v1/delivery/repartidores/candidatos",
        params={"empresa_id": ids["empresa_id"]},
        headers=headers["aprobador1"],
    )
    assert r.status_code == 200
    ids_candidatos = {c["trabajador_id"] for c in r.json()}
    assert ids["trabajador1_id"] not in ids_candidatos
    assert ids["trabajador2_id"] not in ids_candidatos


def test_crear_repartidor_duplicado_es_conflicto(env):
    client, ids, headers, _ = env
    r = client.post(
        "/api/v1/delivery/repartidores",
        headers=headers["aprobador1"],
        json={
            "trabajador_id": ids["trabajador1_id"],
            "sucursal_id": ids["sucursal_id"],
            "vehiculo_tipo": "moto",
        },
    )
    assert r.status_code == 409


def test_repartidor_sin_permiso_de_despacho_no_puede_listar_todos(env):
    client, ids, headers, _ = env
    # `kevinrep` solo tiene `delivery.repartir`, ni leer ni despachar.
    r = client.get("/api/v1/delivery/repartidores", headers=headers["kevinrep"])
    assert r.status_code == 403


# --- Tablero ----------------------------------------------------------------------
def test_tablero_muestra_venta_lista_y_la_saca_al_asignar(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        venta = _crear_venta_delivery(s, ids)
        venta_id = str(venta.id)

    r = client.get(
        "/api/v1/delivery/tablero",
        params={"sucursal_id": ids["sucursal_id"]},
        headers=headers["aprobador1"],
    )
    assert r.status_code == 200
    sin_asignar = [v["id"] for v in r.json()["sin_asignar"]]
    assert venta_id in sin_asignar

    r2 = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [venta_id],
        },
    )
    assert r2.status_code == 201, r2.text

    r3 = client.get(
        "/api/v1/delivery/tablero",
        params={"sucursal_id": ids["sucursal_id"]},
        headers=headers["aprobador1"],
    )
    assert venta_id not in [v["id"] for v in r3.json()["sin_asignar"]]


def test_tablero_no_muestra_pedido_a_medio_preparar(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        _crear_venta_delivery(s, ids, estados_items=("pendiente",))

    r = client.get(
        "/api/v1/delivery/tablero",
        params={"sucursal_id": ids["sucursal_id"]},
        headers=headers["aprobador1"],
    )
    assert r.json()["sin_asignar"] == []


# --- Crear ruta ---------------------------------------------------------------
def test_crear_ruta_sin_ubicacion_es_rechazada(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        venta = _crear_venta_delivery(s, ids, con_ubicacion=False)
        venta_id = str(venta.id)

    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [venta_id],
        },
    )
    assert r.status_code == 409
    assert "ancl" in r.json()["detail"]


def test_crear_ruta_optimiza_por_heuristica_sin_google(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        v1 = _crear_venta_delivery(s, ids)
        v2 = _crear_venta_delivery(s, ids)

    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [str(v1.id), str(v2.id)],
        },
    )
    assert r.status_code == 201, r.text
    ruta = r.json()
    assert ruta["optimizada_por"] == "heuristica"
    assert ruta["distancia_m"] is not None
    assert ruta["estado"] == "planificada"


def test_crear_ruta_respeta_el_orden_manual_sin_optimizar(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        v1 = _crear_venta_delivery(s, ids)
        v2 = _crear_venta_delivery(s, ids)

    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [str(v1.id), str(v2.id)],
            "optimizar": False,
        },
    )
    assert r.status_code == 201
    assert r.json()["optimizada_por"] == "manual"


def test_no_se_rutea_una_venta_ya_asignada_dos_veces(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        venta = _crear_venta_delivery(s, ids)
        venta_id = str(venta.id)

    r1 = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [venta_id],
        },
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor2_id"],
            "venta_ids": [venta_id],
        },
    )
    assert r2.status_code == 409


def test_ruta_supera_el_maximo_de_paradas(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        venta_ids = [str(_crear_venta_delivery(s, ids).id) for _ in range(11)]

    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": venta_ids,
        },
    )
    assert r.status_code == 409


# --- Ciclo completo: iniciar → entregar → sales.venta_entregada -----------------
def _crear_y_asignar_ruta(client, ids, headers, TestSession, repartidor_key="repartidor1_id"):
    with TestSession() as s:
        venta = _crear_venta_delivery(s, ids)
        venta_id = str(venta.id)
    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids[repartidor_key],
            "venta_ids": [venta_id],
        },
    )
    assert r.status_code == 201, r.text
    ruta = r.json()
    with TestSession() as s:
        entrega = s.scalar(select(Entrega).where(Entrega.ruta_id == uuid.UUID(ruta["id"])))
        entrega_id = str(entrega.id)
    return venta_id, ruta["id"], entrega_id


def test_iniciar_entregar_marca_la_venta_entregada_por_evento(env):
    client, ids, headers, TestSession = env
    venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r_iniciar = client.post(
        f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"]
    )
    assert r_iniciar.status_code == 200
    assert r_iniciar.json()["estado"] == "en_curso"

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.estado == "en_ruta"
        assert entrega.eta_at is not None

    r_entregar = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["kevinrep"],
        json={"lat": "-6.49", "lng": "-76.36"},
    )
    assert r_entregar.status_code == 200, r_entregar.text
    assert r_entregar.json()["estado"] == "entregada"

    # `sales` se enteró por evento: el ítem del pedido llegó a `entregado`
    # vía `cumplimiento.registrar_entrega`, sin que `delivery` importara
    # su dominio.
    with TestSession() as s:
        item = s.scalar(select(VentaItem).where(VentaItem.venta_id == uuid.UUID(venta_id)))
        assert item.estado_preparacion == "entregado"
        venta = s.get(Venta, uuid.UUID(venta_id))
        assert venta.repartidor_externo_plataforma is None


def test_repartidor_ajeno_no_puede_entregar_la_ruta_de_otro(env):
    client, ids, headers, TestSession = env
    _venta_id, _ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["anarep"],
        json={},
    )
    assert r.status_code == 403


def test_despacho_puede_registrar_la_entrega_en_nombre_del_repartidor(env):
    client, ids, headers, TestSession = env
    venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    r = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["aprobador1"],
        json={},
    )
    assert r.status_code == 200
    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        # RN-CUP-007: quien queda registrado como repartidor es el dueño de
        # la ruta, aunque haya sido despacho quien tocó el botón.
        assert str(entrega.entregado_por) == ids["usuario_rep1_id"]


def test_entregar_es_idempotente(env):
    client, ids, headers, TestSession = env
    venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["kevinrep"],
        json={},
    )
    r2 = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["kevinrep"],
        json={},
    )
    assert r2.status_code == 200
    assert r2.json()["estado"] == "entregada"


# --- Fallar / reintentar / cerrar ------------------------------------------------
def test_fallar_sin_detalle_en_otro_es_rechazado(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    r = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/fallar",
        headers=headers["kevinrep"],
        json={"motivo": "otro"},
    )
    assert r.status_code == 409


def test_fallar_no_marca_el_item_entregado_y_permite_reintentar(env):
    client, ids, headers, TestSession = env
    venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    r = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/fallar",
        headers=headers["kevinrep"],
        json={"motivo": "cliente_ausente"},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "fallida"

    with TestSession() as s:
        item = s.scalar(select(VentaItem).where(VentaItem.venta_id == uuid.UUID(venta_id)))
        assert item.estado_preparacion == "listo"

    r_reintentar = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/reintentar",
        headers=headers["aprobador1"],
    )
    assert r_reintentar.status_code == 200
    cuerpo = r_reintentar.json()
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["intentos"] == 2
    assert cuerpo["ruta_id"] is None


def test_cerrar_una_entrega_fallida(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/fallar",
        headers=headers["kevinrep"],
        json={"motivo": "no_contesta"},
    )
    r = client.post(f"/api/v1/delivery/entregas/{entrega_id}/cerrar", headers=headers["aprobador1"])
    assert r.status_code == 200
    assert r.json()["estado"] == "cancelada"


# --- Finalizar / cancelar ruta ---------------------------------------------------
def test_finalizar_con_parada_pendiente_es_conflicto(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, _entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/finalizar", headers=headers["aprobador1"])
    assert r.status_code == 409


def test_finalizar_cuando_todo_se_resolvio(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["kevinrep"],
        json={},
    )
    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/finalizar", headers=headers["aprobador1"])
    assert r.status_code == 200
    assert r.json()["estado"] == "finalizada"


def test_cancelar_ruta_planificada_libera_las_entregas(env):
    client, ids, headers, TestSession = env
    venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/cancelar", headers=headers["aprobador1"])
    assert r.status_code == 200
    assert r.json()["estado"] == "cancelada"
    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.estado == "pendiente"
        assert entrega.ruta_id is None


def test_no_se_cancela_una_ruta_en_curso(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, _entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/cancelar", headers=headers["aprobador1"])
    assert r.status_code == 409


# --- Convergencia con sales (KDS y anulación) ------------------------------------
def test_entrega_desde_el_kds_cierra_la_entrega_de_delivery(env):
    """El despacho marca la venta entregada por `POST
    /sales/ventas/{id}/entrega` (el botón del KDS) en vez de por el
    tablero de reparto: `delivery` se entera por `sales.venta_entregada`
    y cierra la entrega abierta sola (ADR-098)."""
    client, ids, headers, TestSession = env
    venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    r = client.post(f"/api/v1/sales/ventas/{venta_id}/entrega", headers=headers["aprobador1"])
    assert r.status_code == 200

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.estado == "entregada"


def test_anular_la_venta_cancela_la_entrega_pendiente(env):
    client, ids, headers, TestSession = env
    with TestSession() as s:
        # `POST /ventas/{id}/anular` solo anula una orden no pagada
        # (RN-COM-005/RN-CUP-012): la venta tiene que seguir en `orden`.
        venta = _crear_venta_delivery(s, ids, estado="orden")
        venta_id = str(venta.id)

    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [venta_id],
        },
    )
    ruta_id = r.json()["id"]
    with TestSession() as s:
        entrega = s.scalar(select(Entrega).where(Entrega.ruta_id == uuid.UUID(ruta_id)))
        entrega_id = str(entrega.id)

    r_anular = client.post(f"/api/v1/sales/ventas/{venta_id}/anular", headers=headers["aprobador1"])
    assert r_anular.status_code == 200

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.estado == "cancelada"


# --- GPS (ADR-098, RN-DLV-007) ---------------------------------------------------
def test_ping_fuera_de_ruta_en_curso_es_conflicto(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, _entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r = client.post(
        f"/api/v1/delivery/rutas/{ruta_id}/posiciones",
        headers=headers["kevinrep"],
        json={"lat": "-6.49", "lng": "-76.36", "registrado_at": "2026-09-09T12:00:00Z"},
    )
    assert r.status_code == 409


def test_repartidor_ajeno_no_puede_pinguear_la_ruta_de_otro(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, _entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    r = client.post(
        f"/api/v1/delivery/rutas/{ruta_id}/posiciones",
        headers=headers["anarep"],
        json={"lat": "-6.49", "lng": "-76.36", "registrado_at": "2026-09-09T12:00:00Z"},
    )
    assert r.status_code == 403


def test_ping_actualiza_la_ultima_posicion_y_el_eta_de_la_proxima_parada(env):
    client, ids, headers, TestSession = env
    _venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    with TestSession() as s:
        eta_inicial = s.get(Entrega, uuid.UUID(entrega_id)).eta_at

    r = client.post(
        f"/api/v1/delivery/rutas/{ruta_id}/posiciones",
        headers=headers["kevinrep"],
        json={
            "lat": "-6.4888",
            "lng": "-76.3611",
            "precision_m": 12,
            "registrado_at": "2026-09-09T12:05:00Z",
        },
    )
    assert r.status_code == 204

    with TestSession() as s:
        ruta = s.get(RutaReparto, uuid.UUID(ruta_id))
        assert ruta.ultima_lat == Decimal("-6.488800")
        assert ruta.ultima_lng == Decimal("-76.361100")
        assert ruta.ultima_precision_m == 12
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.eta_at is not None
        assert entrega.eta_at != eta_inicial


# --- Ruteo real contra Google, con fallback (ADR-098) ----------------------------
def test_crear_ruta_usa_google_cuando_esta_habilitado(env, monkeypatch):
    from src.modules.delivery.application import ruteo

    client, ids, headers, TestSession = env
    with TestSession() as s:
        v1 = _crear_venta_delivery(s, ids)
        v2 = _crear_venta_delivery(s, ids)

    def _google_falso(origen, paradas):
        from src.shared.integrations.google import RutaCalculada
        from src.shared.integrations.google import Tramo as TramoGoogle

        return RutaCalculada(
            orden=[1, 0],
            tramos=[TramoGoogle(1000, 120), TramoGoogle(1500, 180)],
            distancia_m=3000,
            duracion_seg=400,
            polyline="polilinea-de-prueba",
        )

    monkeypatch.setattr(ruteo, "google_habilitado", lambda: True)
    monkeypatch.setattr(ruteo, "google_ruta_optima", _google_falso)

    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [str(v1.id), str(v2.id)],
        },
    )
    assert r.status_code == 201, r.text
    ruta = r.json()
    assert ruta["optimizada_por"] == "google"
    assert ruta["polyline"] == "polilinea-de-prueba"
    assert ruta["distancia_m"] == 3000


def test_crear_ruta_cae_a_heuristica_si_google_falla(env, monkeypatch):
    from src.modules.delivery.application import ruteo
    from src.shared.integrations.google import RutasError

    client, ids, headers, TestSession = env
    with TestSession() as s:
        v1 = _crear_venta_delivery(s, ids)

    def _google_explota(origen, paradas):
        raise RutasError("Google no responde")

    monkeypatch.setattr(ruteo, "google_habilitado", lambda: True)
    monkeypatch.setattr(ruteo, "google_ruta_optima", _google_explota)

    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor1_id"],
            "venta_ids": [str(v1.id)],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["optimizada_por"] == "heuristica"


# --- Purgas periódicas (ADR-098) --------------------------------------------------
def test_purgar_posiciones_borra_solo_lo_viejo(env, monkeypatch):
    from src.modules.delivery.application import tasks as delivery_tasks
    from src.modules.delivery.infrastructure.models import PosicionRepartidor

    client, ids, headers, TestSession = env
    monkeypatch.setattr(delivery_tasks, "session_factory", TestSession)
    _venta_id, ruta_id, _entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    hace_40_dias = datetime.now(UTC) - timedelta(days=40)
    hace_1_dia = datetime.now(UTC) - timedelta(days=1)
    with TestSession() as s:
        ruta_uuid = uuid.UUID(ruta_id)
        repartidor_id = s.get(RutaReparto, ruta_uuid).repartidor_id
        s.add_all(
            [
                PosicionRepartidor(
                    ruta_id=ruta_uuid,
                    repartidor_id=repartidor_id,
                    lat=Decimal("-6.49"),
                    lng=Decimal("-76.36"),
                    registrado_at=hace_40_dias,
                ),
                PosicionRepartidor(
                    ruta_id=ruta_uuid,
                    repartidor_id=repartidor_id,
                    lat=Decimal("-6.49"),
                    lng=Decimal("-76.36"),
                    registrado_at=hace_1_dia,
                ),
            ]
        )
        s.commit()

    borradas = delivery_tasks.purgar_posiciones()
    assert borradas == 1

    with TestSession() as s:
        restantes = s.scalars(select(PosicionRepartidor)).all()
        assert len(restantes) == 1


def test_purgar_evidencias_vacia_solo_las_resueltas_y_vencidas(env, monkeypatch):
    from src.modules.delivery.application import tasks as delivery_tasks

    client, ids, headers, TestSession = env
    monkeypatch.setattr(delivery_tasks, "session_factory", TestSession)
    _venta_id, ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    r = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["kevinrep"],
        json={"foto": base64.b64encode(b"foto-de-prueba").decode()},
    )
    assert r.status_code == 200

    hace_100_dias = datetime.now(UTC) - timedelta(days=100)
    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.evidencia_foto == b"foto-de-prueba"
        # Se resolvió "hoy": todavía no toca purgarla.
        assert delivery_tasks.purgar_evidencias() == 0
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.evidencia_foto == b"foto-de-prueba"
        # Se fuerza la antigüedad para simular que ya pasó el plazo.
        entrega.updated_at = hace_100_dias
        s.commit()

    assert delivery_tasks.purgar_evidencias() == 1
    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.evidencia_foto is None
        assert entrega.estado == "entregada"
