"""Mesas del salón por API: alta, edición y retiro (ADR-018, ADR-069).

El caso de uso ya se prueba a fondo en `test_pdv_slice.py` (numeración,
mapa de ocupación, guardas de orden abierta). Acá se prueba lo que solo
existe en la capa HTTP: que el número lo asigna el sistema y nunca lo
manda el cliente, que el plano no deja pisar una celda ocupada, el alcance
por tenant (RN-MDC-004/005/006) y los permisos.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401  (puebla Base.metadata)
from src.core.app import create_app
from src.core.database import Base
from src.modules.sales.infrastructure.models import Mesa, PuntoVenta, Venta
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Sucursal, Usuario
from src.shared.models.audit_log import AuditLog
from tests.conftest import auth_headers

RUTA = "/api/v1/sales/mesas"


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
        sucursales = list(s.scalars(select(Sucursal).order_by(Sucursal.nombre)))
        ids["sucursal_id"] = str(sucursales[0].id)
        ids["otra_sucursal_id"] = str(sucursales[1].id)
        ids["admin_id"] = s.scalar(select(Usuario.id).where(Usuario.username == "admin"))
        cabeceras = auth_headers(s)
        cabeceras_cajero = auth_headers(s, username="cajero1")
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
        yield c, cabeceras, cabeceras_cajero, ids, TestSession


def _abrir_orden_en(TestSession, sucursal_id: str, usuario_id, mesa_id) -> None:
    """Inserta una venta `orden` directo en la mesa, sin pasar por el
    checkout completo (caja, catálogo, precios) — lo único que importa acá
    es que la mesa quede con una orden abierta."""
    with TestSession() as s:
        punto = PuntoVenta(
            sucursal_id=uuid.UUID(sucursal_id),
            canal="trabajador",
            politica_pago="al_finalizar",
            serie_boleta="B001",
            serie_factura="F001",
            modalidades_habilitadas=["mesa"],
        )
        s.add(punto)
        s.flush()
        s.add(
            Venta(
                sucursal_id=uuid.UUID(sucursal_id),
                fecha_orden=date.today(),
                numero_orden=1,
                punto_venta_id=punto.id,
                canal="pdv",
                modalidad="mesa",
                estado="orden",
                usuario_id=usuario_id,
                total=Decimal("0.00"),
                idempotency_key="orden-abierta-test",
                mesa_id=uuid.UUID(mesa_id),
            )
        )
        s.commit()


# --- Alta y numeración automática (RN-MDC-004) -------------------------------
def test_crear_mesa_numera_automatico_y_secuencial(env):
    client, headers, _, ids, _ = env
    uno = client.post(RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]})
    dos = client.post(RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]})
    assert uno.status_code == 201, uno.text
    assert uno.json()["numero"] == 1
    assert dos.json()["numero"] == 2


def test_crear_mesa_no_acepta_numero_del_cliente(env):
    """El body no tiene `numero`: mandarlo no hace nada — lo asigna
    siempre el sistema, campo extra o no."""
    client, headers, _, ids, _ = env
    r = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"], "numero": 99}
    )
    assert r.status_code == 201, r.text
    assert r.json()["numero"] == 1


def test_crear_mesa_en_celda_ocupada_choca(env):
    client, headers, _, ids, _ = env
    r1 = client.post(
        RUTA,
        headers=headers,
        json={"sucursal_id": ids["sucursal_id"], "pos_x": 0, "pos_y": 0},
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        RUTA,
        headers=headers,
        json={"sucursal_id": ids["sucursal_id"], "pos_x": 0, "pos_y": 0},
    )
    assert r2.status_code == 409, r2.text


def test_la_numeracion_es_por_sucursal_no_por_grupo(env):
    """Dos sucursales de la misma empresa numeran cada una desde 1 — el
    correlativo es del salón, no de la empresa (RN-MDC-004)."""
    client, headers, _, ids, _ = env
    aqui = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    alla = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["otra_sucursal_id"]}
    ).json()
    assert aqui["numero"] == 1
    assert alla["numero"] == 1


# --- Edición (RN-MDC-005) ----------------------------------------------------
def test_editar_mesa_zona_capacidad_y_celda(env):
    client, headers, _, ids, _ = env
    mesa = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()

    r = client.patch(
        f"{RUTA}/{mesa['id']}",
        headers=headers,
        json={"zona": "Terraza", "capacidad": 6, "pos_x": 3, "pos_y": 1},
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["zona"] == "Terraza"
    assert cuerpo["capacidad"] == 6
    assert cuerpo["pos_x"] == 3
    assert cuerpo["pos_y"] == 1
    assert cuerpo["numero"] == mesa["numero"]  # el número nunca cambia


def test_editar_mesa_no_pisa_otra_celda(env):
    client, headers, _, ids, _ = env
    uno = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    dos = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()

    r = client.patch(
        f"{RUTA}/{dos['id']}",
        headers=headers,
        json={"pos_x": uno["pos_x"], "pos_y": uno["pos_y"]},
    )
    assert r.status_code == 409, r.text


def test_editar_mesa_con_orden_abierta_se_rechaza(env):
    client, headers, _, ids, TestSession = env
    mesa = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    _abrir_orden_en(TestSession, ids["sucursal_id"], ids["admin_id"], mesa["id"])

    r = client.patch(f"{RUTA}/{mesa['id']}", headers=headers, json={"zona": "Terraza"})
    assert r.status_code == 409, r.text


def test_editar_mesa_inexistente_es_404(env):
    client, headers, _, _, _ = env
    r = client.patch(
        f"{RUTA}/00000000-0000-0000-0000-000000000001",
        headers=headers,
        json={"zona": "Terraza"},
    )
    assert r.status_code == 404, r.text


# --- Retiro (RN-MDC-006) ------------------------------------------------------
def test_eliminar_mesa_borra_y_libera_el_numero(env):
    client, headers, _, ids, _ = env
    uno = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()

    r = client.delete(f"{RUTA}/{uno['id']}", headers=headers)
    assert r.status_code == 204, r.text

    otra = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    assert otra["numero"] == 1


def test_eliminar_mesa_que_no_es_la_ultima_choca(env):
    client, headers, _, ids, _ = env
    uno = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    client.post(RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]})

    r = client.delete(f"{RUTA}/{uno['id']}", headers=headers)
    assert r.status_code == 409, r.text
    assert "2" in r.json()["detail"]


def test_eliminar_mesa_con_orden_abierta_se_rechaza(env):
    client, headers, _, ids, TestSession = env
    mesa = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    _abrir_orden_en(TestSession, ids["sucursal_id"], ids["admin_id"], mesa["id"])

    r = client.delete(f"{RUTA}/{mesa['id']}", headers=headers)
    assert r.status_code == 409, r.text


def test_eliminar_mesa_con_ventas_la_desactiva_sin_borrar_la_fila(env):
    client, headers, _, ids, TestSession = env
    mesa = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    _abrir_orden_en(TestSession, ids["sucursal_id"], ids["admin_id"], mesa["id"])
    with TestSession() as s:
        venta = s.scalar(select(Venta).where(Venta.mesa_id == uuid.UUID(mesa["id"])))
        venta.estado = "pagada"
        s.commit()

    r = client.delete(f"{RUTA}/{mesa['id']}", headers=headers)
    assert r.status_code == 204, r.text

    listado = client.get(RUTA, headers=headers, params={"sucursal_id": ids["sucursal_id"]})
    assert listado.json() == []  # `de_sucursal` filtra activas por defecto

    with TestSession() as s:
        fila = s.get(Mesa, uuid.UUID(mesa["id"]))
        assert fila is not None  # no se borró: hay historia
        assert fila.activa is False


# --- Permisos -----------------------------------------------------------------
def test_el_cajero_lee_pero_no_gestiona_mesas(env):
    client, headers, cajero, ids, _ = env
    mesa = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()

    assert client.post(
        RUTA, headers=cajero, json={"sucursal_id": ids["sucursal_id"]}
    ).status_code == 403
    assert client.patch(
        f"{RUTA}/{mesa['id']}", headers=cajero, json={"zona": "Terraza"}
    ).status_code == 403
    assert client.delete(f"{RUTA}/{mesa['id']}", headers=cajero).status_code == 403
    assert client.get(
        RUTA, headers=cajero, params={"sucursal_id": ids["sucursal_id"]}
    ).status_code == 200


# --- Auditoría -----------------------------------------------------------------
def test_auditoria(env):
    client, headers, _, ids, TestSession = env
    mesa = client.post(
        RUTA, headers=headers, json={"sucursal_id": ids["sucursal_id"]}
    ).json()
    client.patch(f"{RUTA}/{mesa['id']}", headers=headers, json={"zona": "Terraza"})
    client.delete(f"{RUTA}/{mesa['id']}", headers=headers)

    with TestSession() as s:
        acciones = [
            a.accion
            for a in s.scalars(select(AuditLog).where(AuditLog.entidad == "mesa"))
        ]
    assert sorted(acciones) == ["crear", "editar", "eliminar"]
