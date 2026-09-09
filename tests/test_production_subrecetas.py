"""Tests de subrecetas anidadas (RN-PRD-020): una línea del consumo
sugerido cuyo artículo tiene receta BOM propia y no alcanza el disponible
del almacén se marca `requiere_orden_hija`; la orden padre no admite
registrar consumo mientras esa orden hija no llegue a `conforme`.

Fixture con BOM de dos niveles: `masa` (la produce la orden padre) usa
`crema` como insumo, y `crema` a su vez tiene su propia receta (usa
`harina`) — mismo patrón de fixture que `test_production.py`, con un
artículo intermedio nuevo.
"""

import uuid
from datetime import time
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
from src.modules.production.infrastructure.models import ChecklistInocuidadTurno
from src.modules.rrhh.infrastructure.models import Asistencia, Trabajador
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Persona,
    Rol,
    Usuario,
    UsuarioRol,
)
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
        almacen = Almacen(empresa_id=empresa.id, nombre="Producción", tipo="produccion")
        s.add_all([udm, almacen])
        s.flush()

        harina = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=udm.id, tipo="insumo",
        )
        crema = Articulo(
            empresa_id=empresa.id, id_interno="C001", nombre="Crema pastelera",
            unidad_medida_id=udm.id, tipo="subreceta", controla_lote=True,
        )
        masa = Articulo(
            empresa_id=empresa.id, id_interno="M001", nombre="Masa rellena",
            unidad_medida_id=udm.id, tipo="subreceta", controla_lote=True,
        )
        s.add_all([harina, crema, masa])
        s.flush()
        sku_harina = Sku(articulo_id=harina.id, codigo="SKU-HARINA")
        sku_crema = Sku(articulo_id=crema.id, codigo="SKU-CREMA")
        s.add_all([sku_harina, sku_crema, Sku(articulo_id=masa.id, codigo="SKU-MASA")])
        s.flush()

        # Nivel 1: crema se hace con harina (1 kg harina -> 5 kg crema).
        receta_crema = Receta(
            empresa_id=empresa.id, nombre="Crema pastelera (BOM)",
            rendimiento_cantidad=Decimal(5), rendimiento_unidad_medida_id=udm.id,
            articulo_id=crema.id,
        )
        s.add(receta_crema)
        s.flush()
        s.add(RecetaItem(receta_id=receta_crema.id, articulo_id=harina.id, cantidad=Decimal(1)))

        # Nivel 2: masa se hace con crema (2 kg crema -> 10 kg masa).
        receta_masa = Receta(
            empresa_id=empresa.id, nombre="Masa rellena (BOM)",
            rendimiento_cantidad=Decimal(10), rendimiento_unidad_medida_id=udm.id,
            articulo_id=masa.id,
        )
        s.add(receta_masa)
        s.flush()
        s.add(RecetaItem(receta_id=receta_masa.id, articulo_id=crema.id, cantidad=Decimal(2)))
        s.flush()

        # Harina de sobra; crema sin stock — la orden de masa la va a
        # necesitar fabricar antes (RN-PRD-020).
        s.add(Stock(almacen_id=almacen.id, sku_id=sku_harina.id, cantidad=Decimal(1000)))

        jefe_cocina = Usuario(username="jefe1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(jefe_cocina)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "jefe_cocina"))
        s.add(UsuarioRol(usuario_id=jefe_cocina.id, rol_id=rol.id))
        s.flush()

        s.add(
            ChecklistInocuidadTurno(
                almacen_id=almacen.id, fecha=fechas.hoy(), turno="mañana",
                verificado_por=jefe_cocina.id,
                bioseguridad_ok=True, superficies_ok=True, limpieza_intermedia_ok=True,
                equipos_frio=[], plaga_indicio=False, estado="aprobado",
            )
        )

        persona_cocinero = Persona(nombres="Cocinero", apellidos="De Prueba")
        s.add(persona_cocinero)
        s.flush()
        cocinero = Trabajador(
            empresa_id=empresa.id, persona_id=persona_cocinero.id,
            cargo="Cocinero", area="Cocina", tipo_vinculo="planilla",
            fecha_ingreso=fechas.hoy(),
        )
        s.add(cocinero)
        s.flush()
        s.add(Asistencia(
            trabajador_id=cocinero.id, fecha=fechas.hoy(),
            hora_entrada=time(8, 0), hora_salida=time(10, 0),
        ))

        ids.update(
            empresa_id=str(empresa.id), almacen_id=str(almacen.id),
            harina_id=str(harina.id), crema_id=str(crema.id), masa_id=str(masa.id),
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


def _crear_orden_masa(client, headers, ids, key="op-masa-1", cantidad="10"):
    return client.post("/api/v1/production/ordenes", headers=headers, json={
        "articulo_id": ids["masa_id"], "almacen_id": ids["almacen_id"],
        "cantidad_planeada": cantidad, "idempotency_key": key,
    })


def _crear_hija(client, headers, orden_id, ids, key="op-crema-1", cantidad="2"):
    return client.post(
        f"/api/v1/production/ordenes/{orden_id}/ordenes-hijas", headers=headers, json={
            "articulo_id": ids["crema_id"], "cantidad_planeada": cantidad,
            "idempotency_key": key,
        },
    )


def test_consumo_sugerido_marca_requiere_orden_hija(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden_masa(client, h, ids).json()["id"]

    r = client.get(f"/api/v1/production/ordenes/{orden_id}/consumo-sugerido", headers=h)
    assert r.status_code == 200, r.text
    (linea,) = r.json()["items"]
    assert linea["articulo_id"] == ids["crema_id"]
    assert linea["requiere_orden_hija"] is True


def test_consumo_sugerido_no_requiere_hija_con_stock_suficiente(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        sku_crema = s.scalar(
            select(Sku).where(Sku.articulo_id == uuid.UUID(ids["crema_id"]))
        )
        s.add(
            Stock(
                almacen_id=uuid.UUID(ids["almacen_id"]), sku_id=sku_crema.id,
                cantidad=Decimal(100),
            )
        )
        s.commit()

    orden_id = _crear_orden_masa(client, h, ids).json()["id"]
    r = client.get(f"/api/v1/production/ordenes/{orden_id}/consumo-sugerido", headers=h)
    (linea,) = r.json()["items"]
    assert linea["requiere_orden_hija"] is False


def test_crear_orden_hija_liga_orden_padre_id(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden_masa(client, h, ids).json()["id"]

    r = _crear_hija(client, h, orden_id, ids)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["orden_padre_id"] == orden_id
    assert body["origen"] == "subreceta_anidada"
    assert body["articulo_id"] == ids["crema_id"]


def test_detalle_orden_padre_lista_la_hija(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden_masa(client, h, ids).json()["id"]
    hija_id = _crear_hija(client, h, orden_id, ids).json()["id"]

    detalle = client.get(f"/api/v1/production/ordenes/{orden_id}", headers=h).json()
    assert len(detalle["hijas"]) == 1
    assert detalle["hijas"][0]["id"] == hija_id
    assert detalle["hijas"][0]["estado"] == "borrador"


def test_registrar_consumo_bloqueado_por_hija_pendiente_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden_masa(client, h, ids).json()["id"]
    _crear_hija(client, h, orden_id, ids)

    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["crema_id"], "cantidad": "2", "costo_unitario": "5"}],
        },
    )
    assert r.status_code == 409


def test_registrar_consumo_permitido_cuando_hija_queda_conforme(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden_masa(client, h, ids).json()["id"]
    hija_id = _crear_hija(client, h, orden_id, ids).json()["id"]

    # Se produce la hija de punta a punta hasta conforme.
    r = client.post(
        f"/api/v1/production/ordenes/{hija_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["harina_id"], "cantidad": "2", "costo_unitario": "3"}],
        },
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/v1/production/ordenes/{hija_id}/completar", headers=h, json={
            "resultado": "conforme", "cantidad_producida": "2",
        },
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["crema_id"], "cantidad": "2", "costo_unitario": "5"}],
        },
    )
    assert r.status_code == 200, r.text


def test_crear_orden_hija_sin_padre_404(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/production/ordenes/00000000-0000-0000-0000-000000000000/ordenes-hijas",
        headers=h, json={
            "articulo_id": ids["crema_id"], "cantidad_planeada": "2",
            "idempotency_key": "op-crema-huerfana",
        },
    )
    assert r.status_code == 404
