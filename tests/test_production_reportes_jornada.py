"""Tests del reporte de producción de la jornada (RN-DOC-010): se genera
solo con las órdenes que cerraron control de calidad ese día, se
recalcula mientras no esté visado, y una vez visado queda congelado.
Mismo patrón de fixture que `test_production.py` (incluye checklist de
inocuidad aprobado, RN-CDP-005, para que crear la orden no rechace).
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
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
from src.modules.production.application import listeners as production_listeners
from src.modules.production.infrastructure.models import (
    ChecklistInocuidadTurno,
    ReporteProduccion,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import Almacen, Empresa, Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.security import hash_pin
from src.shared import fechas


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(listeners, "session_factory", TestSession)
    monkeypatch.setattr(production_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo", ratio=Decimal(1))
        s.add(udm)
        s.flush()
        # `seed()` ya crea el almacén `produccion` (WH-PROD, bloque
        # `feat/produccion-semilla-y-pantalla-con-permisos`): crear uno propio
        # acá dejaba dos almacenes `tipo=produccion` en la misma empresa, y el
        # barrido genera un reporte por cada uno (`generados == 2` en vez de 1).
        almacen = s.scalar(select(Almacen).where(Almacen.tipo == "produccion"))

        harina = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        masa = Articulo(
            empresa_id=empresa.id, id_interno="M001", nombre="Masa madre",
            unidad_medida_id=udm.id, tipo="subreceta", controla_lote=True,
        )
        s.add_all([harina, masa])
        s.flush()
        sku_harina = Sku(articulo_id=harina.id, codigo="SKU-HARINA")
        s.add(sku_harina)
        s.add(Sku(articulo_id=masa.id, codigo="SKU-MASA"))
        s.flush()

        receta = Receta(
            empresa_id=empresa.id,
            nombre="Masa madre (BOM)", rendimiento_cantidad=Decimal(10),
            rendimiento_unidad_medida_id=udm.id, articulo_id=masa.id,
        )
        s.add(receta)
        s.flush()
        s.add(RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal(1)))
        s.flush()

        s.add(Stock(almacen_id=almacen.id, sku_id=sku_harina.id, cantidad=Decimal(1000)))

        jefe_cocina = Usuario(username="jefe1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(jefe_cocina)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "jefe_cocina"))
        s.add(UsuarioRol(usuario_id=jefe_cocina.id, rol_id=rol.id))
        s.flush()

        # RN-CDP-005: sin esto, crear_orden_produccion rechaza con 409.
        s.add(
            ChecklistInocuidadTurno(
                almacen_id=almacen.id, fecha=fechas.hoy(), turno="mañana",
                verificado_por=jefe_cocina.id,
                bioseguridad_ok=True, superficies_ok=True, limpieza_intermedia_ok=True,
                equipos_frio=[], plaga_indicio=False, estado="aprobado",
            )
        )

        ids.update(
            empresa_id=str(empresa.id), almacen_id=str(almacen.id),
            harina_id=str(harina.id), masa_id=str(masa.id),
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
        yield c, ids, TestSession


def _token(client, username="admin", pin="123456"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_orden(client, headers, ids, key="op-jornada-1", cantidad="10"):
    return client.post("/api/v1/production/ordenes", headers=headers, json={
        "articulo_id": ids["masa_id"], "almacen_id": ids["almacen_id"],
        "cantidad_planeada": cantidad, "idempotency_key": key,
    })


def _generar_reporte(client, headers, ids, fecha=None):
    body = {"almacen_id": ids["almacen_id"]}
    if fecha:
        body["fecha"] = fecha
    return client.post("/api/v1/production/reportes-jornada/generar", headers=headers, json=body)


def test_generar_reporte_sin_ordenes(env):
    client, ids, _ = env
    h = _token(client)
    r = _generar_reporte(client, h, ids)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ordenes"] == []
    assert Decimal(body["merma_total"]) == 0
    assert Decimal(body["costo_total"]) == 0
    assert body["visado_at"] is None


def test_generar_reporte_incluye_orden_completada(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids).json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["harina_id"], "cantidad": "10", "costo_unitario": "2"}],
        },
    )
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
            "resultado": "conforme", "cantidad_producida": "10",
        },
    )

    r = _generar_reporte(client, h, ids)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["ordenes"]) == 1
    assert body["ordenes"][0]["orden_produccion_id"] == orden_id
    assert Decimal(body["costo_total"]) == Decimal("20.0000")  # 10 * 2 de insumos, sin MO


def test_generar_reporte_no_incluye_orden_sin_completar(env):
    client, ids, _ = env
    h = _token(client)
    _crear_orden(client, h, ids)  # se queda en borrador

    r = _generar_reporte(client, h, ids)
    assert r.status_code == 200, r.text
    assert r.json()["ordenes"] == []


def test_generar_reporte_es_idempotente_por_almacen_y_jornada(env):
    client, ids, TestSession = env
    h = _token(client)
    primero = _generar_reporte(client, h, ids).json()["id"]
    segundo = _generar_reporte(client, h, ids).json()["id"]
    assert primero == segundo

    with TestSession() as s:
        assert s.scalar(select(ReporteProduccion)).id == uuid.UUID(primero)


def test_visar_reporte(env):
    client, ids, _ = env
    h = _token(client)
    reporte_id = _generar_reporte(client, h, ids).json()["id"]

    r = client.post(
        f"/api/v1/production/reportes-jornada/{reporte_id}/visar", headers=h,
        json={"observaciones": "Jornada tranquila"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["visado_at"] is not None
    assert body["visado_por"] is not None
    assert body["observaciones"] == "Jornada tranquila"


def test_visar_reporte_ya_visado_409(env):
    client, ids, _ = env
    h = _token(client)
    reporte_id = _generar_reporte(client, h, ids).json()["id"]
    client.post(f"/api/v1/production/reportes-jornada/{reporte_id}/visar", headers=h, json={})

    r = client.post(f"/api/v1/production/reportes-jornada/{reporte_id}/visar", headers=h, json={})
    assert r.status_code == 409


def test_generar_no_recalcula_un_reporte_ya_visado(env):
    client, ids, TestSession = env
    h = _token(client)
    reporte_id = _generar_reporte(client, h, ids).json()["id"]
    client.post(f"/api/v1/production/reportes-jornada/{reporte_id}/visar", headers=h, json={})

    orden_id = _crear_orden(client, h, ids).json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["harina_id"], "cantidad": "10", "costo_unitario": "2"}],
        },
    )
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
            "resultado": "conforme", "cantidad_producida": "10",
        },
    )

    r = _generar_reporte(client, h, ids)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == reporte_id
    assert r.json()["ordenes"] == []  # sigue congelado: no ve la orden nueva


def test_listar_reportes_jornada(env):
    client, ids, _ = env
    h = _token(client)
    _generar_reporte(client, h, ids)
    listado = client.get("/api/v1/production/reportes-jornada", headers=h).json()
    assert listado["total"] == 1


def test_visar_reporte_sin_permiso_403(env):
    client, ids, TestSession = env
    h = _token(client)
    reporte_id = _generar_reporte(client, h, ids).json()["id"]

    with TestSession() as s:
        cajero = Usuario(username="cajero_jornada", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cajero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol.id))
        s.commit()

    h_cajero = _token(client, "cajero_jornada", "222222")
    r = client.post(
        f"/api/v1/production/reportes-jornada/{reporte_id}/visar", headers=h_cajero, json={}
    )
    assert r.status_code == 403


def test_barrido_genera_reporte_pasada_la_hora_de_cierre(env, monkeypatch):
    """Semilla `production_hora_cierre_jornada` = 22:00 (sin `parametro_
    empresa` propio en este test): a las 23:00 ya cerró."""
    _, ids, TestSession = env
    from src.modules.production.application import tasks

    monkeypatch.setattr(tasks, "session_factory", TestSession)
    tarde = fechas.ahora().replace(hour=23, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(fechas, "ahora", lambda: tarde)

    generados = tasks.generar_reportes_de_jornada_vencidos()
    assert generados == 1
    with TestSession() as s:
        reporte = s.scalar(select(ReporteProduccion))
        assert reporte is not None
        assert str(reporte.almacen_id) == ids["almacen_id"]


def test_barrido_no_genera_antes_de_la_hora_de_cierre(env, monkeypatch):
    _, _ids, TestSession = env
    from src.modules.production.application import tasks

    monkeypatch.setattr(tasks, "session_factory", TestSession)
    temprano = fechas.ahora().replace(hour=6, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(fechas, "ahora", lambda: temprano)

    generados = tasks.generar_reportes_de_jornada_vencidos()
    assert generados == 0
    with TestSession() as s:
        assert s.scalar(select(ReporteProduccion)) is None
