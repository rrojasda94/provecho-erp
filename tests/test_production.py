"""Tests del slice production core: orden de producción (crear → consumo
→ completar). SQLite en memoria + override de get_db, mismo patrón que
test_purchases.py.
"""

import uuid
from datetime import time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.core.events import event_bus
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Lote,
    Receta,
    RecetaItem,
    Sku,
    UnidadMedida,
)
from src.modules.production.application import listeners as production_listeners
from src.modules.production.infrastructure.models import OrdenProduccion
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
from src.shared.models.audit_log import AuditLog


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
        masa = Articulo(
            empresa_id=empresa.id, id_interno="M001", nombre="Masa madre",
            unidad_medida_id=udm.id, tipo="subreceta", controla_lote=True,
        )
        s.add_all([harina, masa])
        s.flush()
        s.add(Sku(articulo_id=harina.id, codigo="SKU-HARINA"))
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

        # Stock inicial de harina para poder consumirla.
        from src.modules.inventory.infrastructure.models import Stock
        sku_harina = s.scalar(select(Sku).where(Sku.articulo_id == harina.id))
        s.add(Stock(almacen_id=almacen.id, sku_id=sku_harina.id, cantidad=Decimal(1000)))

        jefe_cocina = Usuario(username="jefe1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(jefe_cocina)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "jefe_cocina"))
        s.add(UsuarioRol(usuario_id=jefe_cocina.id, rol_id=rol.id))

        # Trabajador con 2 horas asistidas hoy (08:00-10:00), para completar
        # con `trabajadores` en vez del `horas_hombre` tipeado de antes.
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
            harina_id=str(harina.id), masa_id=str(masa.id),
            cocinero_id=str(cocinero.id),
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


def _crear_orden(client, headers, ids, idempotency_key="op-key-1", cantidad="10"):
    return client.post("/api/v1/production/ordenes", headers=headers, json={
        "articulo_id": ids["masa_id"],
        "almacen_id": ids["almacen_id"],
        "cantidad_planeada": cantidad,
        "idempotency_key": idempotency_key,
    })


def _consumo_body(ids, cantidad="10", costo="2.00"):
    return {
        "items": [
            {"articulo_id": ids["harina_id"], "cantidad": cantidad, "costo_unitario": costo}
        ],
    }


def _trabajadores_body(ids, horas=None):
    """Sin `horas`, se imputan todas las asistidas hoy (2h, ver fixture
    `env`) — mismo resultado que el viejo `"horas_hombre": "2"`."""
    trabajador = {"trabajador_id": ids["cocinero_id"]}
    if horas is not None:
        trabajador["horas"] = horas
    return [trabajador]


def _adjuntar_evidencia(client, headers, orden_id, nombre="evidencia.jpg"):
    return client.post(
        f"/api/v1/production/ordenes/{orden_id}/evidencia", headers=headers, json={
            "nombre": nombre, "mime_type": "image/jpeg", "tamano_bytes": 1024,
            "url_storage": "https://x/evidencia.jpg",
        },
    )


def test_crear_orden_sin_receta_409(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/production/ordenes", headers=h, json={
        "articulo_id": ids["harina_id"],  # harina no tiene receta propia
        "almacen_id": ids["almacen_id"],
        "cantidad_planeada": "5",
        "idempotency_key": "op-sin-receta",
    })
    assert r.status_code == 409


def test_flujo_completo_conforme_actualiza_stock_y_costo(env):
    client, ids, TestSession = env
    h = _token(client)
    orden = _crear_orden(client, h, ids)
    assert orden.status_code == 201
    orden_id = orden.json()["id"]
    assert orden.json()["estado"] == "borrador"

    consumo = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h,
        json=_consumo_body(ids),
    )
    assert consumo.status_code == 200
    assert consumo.json()["estado"] == "en_proceso"

    completar = client.post(
        f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
            "resultado": "conforme", "cantidad_producida": "10",
            "trabajadores": _trabajadores_body(ids),
        },
    )
    assert completar.status_code == 200
    body = completar.json()
    assert body["estado"] == "conforme"
    assert Decimal(body["costo_insumos"]) == Decimal("20.00")
    # 2 horas * 15.00 (tarifa semilla) = 30; (20+30)/10 producido = 5.
    assert Decimal(body["costo_real_unitario"]) == Decimal("5.0000000000")

    stock = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['almacen_id']}", headers=h
    ).json()["items"]
    por_sku = {s["sku_id"]: Decimal(s["cantidad"]) for s in stock}
    assert Decimal("990") in por_sku.values()  # harina: 1000 - 10
    assert Decimal("10") in por_sku.values()  # masa producida

    with TestSession() as s:
        masa = s.get(Articulo, uuid.UUID(ids["masa_id"]))
        assert masa.costo_promedio == Decimal("5.0000")


def test_completar_no_conforme_reprocesado_sin_merma(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-2").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_reprocesado",
    })
    assert r.status_code == 200
    assert r.json()["estado"] == "no_conforme_reprocesado"
    assert r.json()["merma_cantidad"] is None


def test_completar_desechado_sin_evidencia_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-3").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_desechado", "merma_cantidad": "10",
        "merma_motivo": "contaminación",
    })
    assert r.status_code == 409


def test_completar_desechado_con_evidencia_ok(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-4").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    assert _adjuntar_evidencia(client, h, orden_id).status_code == 201
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_desechado", "merma_cantidad": "10",
        "merma_motivo": "contaminación",
    })
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "no_conforme_desechado"
    assert r.json()["merma_motivo"] == "contaminación"


# --- Evidencia de destrucción como archivo (feat/produccion-evidencia-como-archivo) ---
def test_adjuntar_evidencia_setea_evidencia_archivo_id_en_la_orden(env):
    client, ids, TestSession = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-evidencia-1").json()["id"]
    r = _adjuntar_evidencia(client, h, orden_id)
    assert r.status_code == 201, r.text
    archivo_id = r.json()["id"]

    detalle = client.get(f"/api/v1/production/ordenes/{orden_id}", headers=h).json()
    assert detalle["evidencia_archivo_id"] == archivo_id


def test_adjuntar_evidencia_mime_no_admitido_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-evidencia-2").json()["id"]
    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/evidencia", headers=h, json={
            "nombre": "planilla.xlsx", "mime_type": "application/vnd.ms-excel",
            "tamano_bytes": 1024, "url_storage": "https://x/planilla.xlsx",
        },
    )
    assert r.status_code == 409


def test_adjuntar_evidencia_supera_tamano_maximo_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-evidencia-3").json()["id"]
    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/evidencia", headers=h, json={
            "nombre": "video.mp4", "mime_type": "video/mp4",
            "tamano_bytes": 200 * 1024 * 1024, "url_storage": "https://x/video.mp4",
        },
    )
    assert r.status_code == 409


def test_adjuntar_evidencia_registra_auditoria(env):
    client, ids, TestSession = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-evidencia-4").json()["id"]
    _adjuntar_evidencia(client, h, orden_id)

    with TestSession() as s:
        accion = s.scalar(
            select(AuditLog.accion).where(
                AuditLog.entidad == "orden_produccion",
                AuditLog.entidad_id == uuid.UUID(orden_id),
                AuditLog.accion == "adjuntar_evidencia",
            )
        )
    assert accion == "adjuntar_evidencia"


# --- Horas-hombre desde asistencia de RRHH (feat/produccion-horas-hombre-desde-rrhh) ---
def test_completar_sin_horas_no_imputa_mano_de_obra(env):
    """`trabajadores` vacío (default) sigue siendo válido: horas_hombre=0,
    igual que antes con `horas_hombre` ausente."""
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-horas-1").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
    })
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["costo_mano_obra"]) == Decimal("0")


def test_completar_con_horas_explicitas_dentro_de_lo_asistido(env):
    client, ids, TestSession = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-horas-2").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": _trabajadores_body(ids, horas="1.5"),
    })
    assert r.status_code == 200, r.text
    # 1.5 horas * 15.00 (tarifa semilla) = 22.5; (20 + 22.5) / 10 = 4.25.
    assert Decimal(r.json()["costo_real_unitario"]) == Decimal("4.2500000000")

    detalle = client.get(f"/api/v1/production/ordenes/{orden_id}", headers=h).json()
    (trabajador,) = detalle["trabajadores"]
    assert trabajador["trabajador_id"] == ids["cocinero_id"]
    assert Decimal(trabajador["horas"]) == Decimal("1.50")


def test_completar_horas_superan_lo_asistido_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-horas-3").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        # El cocinero de la fixture solo asistió 2 horas hoy.
        "trabajadores": _trabajadores_body(ids, horas="5"),
    })
    assert r.status_code == 409


def test_completar_trabajador_sin_asistencia_hoy_409(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        persona = Persona(nombres="Sin", apellidos="Asistencia")
        s.add(persona)
        s.flush()
        trabajador = Trabajador(
            empresa_id=uuid.UUID(ids["empresa_id"]), persona_id=persona.id,
            cargo="Cocinero", area="Cocina", tipo_vinculo="planilla",
            fecha_ingreso=fechas.hoy(),
        )
        s.add(trabajador)
        s.commit()
        trabajador_id = str(trabajador.id)

    orden_id = _crear_orden(client, h, ids, idempotency_key="op-horas-4").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": [{"trabajador_id": trabajador_id}],
    })
    assert r.status_code == 409


# --- Orden por necesidad (feat/produccion-orden-por-necesidad) ---
def _publicar_stock_bajo_minimo(session, *, almacen_id, sku_id, cantidad="2", stock_minimo="5"):
    event_bus.publish(
        "inventory.stock_bajo_minimo",
        {
            "almacen_id": str(almacen_id), "sku_id": str(sku_id),
            "cantidad": cantidad, "stock_minimo": stock_minimo, "usuario_id": None,
        },
        session=session,
    )


def test_stock_bajo_minimo_crea_orden_ajuste_por_necesidad(env):
    """RN-PRD-007/011: sin nadie tipeando nada, la cocina ve una orden lista
    apenas el central cruza el mínimo de una subreceta."""
    client, ids, TestSession = env
    with TestSession() as s:
        empresa_id = uuid.UUID(ids["empresa_id"])
        almacen_sucursal = Almacen(
            empresa_id=empresa_id, nombre="Sucursal Test", tipo="sucursal"
        )
        s.add(almacen_sucursal)
        s.flush()
        sku_masa = s.scalar(select(Sku).where(Sku.articulo_id == uuid.UUID(ids["masa_id"])))
        _publicar_stock_bajo_minimo(
            s, almacen_id=almacen_sucursal.id, sku_id=sku_masa.id,
            cantidad="2", stock_minimo="5",
        )
        s.commit()

    with TestSession() as s:
        orden = s.scalar(
            select(OrdenProduccion).where(
                OrdenProduccion.articulo_id == uuid.UUID(ids["masa_id"]),
                OrdenProduccion.almacen_id == uuid.UUID(ids["almacen_id"]),
            )
        )
        assert orden is not None
        assert orden.origen == "ajuste_por_necesidad"
        assert orden.creado_por is None
        # factor semilla 2: 5*2 - 2 = 8, redondeado al rendimiento (10) → 10.
        assert orden.cantidad_planeada == Decimal("10.0000")
        assert orden.estado == "borrador"


def test_stock_bajo_minimo_sin_almacen_produccion_no_crea_nada(env):
    client, ids, TestSession = env
    with TestSession() as s:
        empresa_base = s.get(Empresa, uuid.UUID(ids["empresa_id"]))
        otra = Empresa(
            grupo_id=empresa_base.grupo_id, ruc="20600000010",
            razon_social="Sin Cocina EIRL", domicilio_fiscal="Lima",
            tipo="operativa", zona_tributaria="amazonia_ley27037",
        )
        s.add(otra)
        s.flush()
        almacen_sucursal = Almacen(
            empresa_id=otra.id, nombre="Sucursal Sin Cocina", tipo="sucursal"
        )
        s.add(almacen_sucursal)
        s.flush()
        sku_masa = s.scalar(select(Sku).where(Sku.articulo_id == uuid.UUID(ids["masa_id"])))
        _publicar_stock_bajo_minimo(s, almacen_id=almacen_sucursal.id, sku_id=sku_masa.id)
        s.commit()
        otra_id = otra.id

    with TestSession() as s:
        assert s.scalar(
            select(OrdenProduccion)
            .join(Almacen, Almacen.id == OrdenProduccion.almacen_id)
            .where(Almacen.empresa_id == otra_id)
        ) is None


def test_stock_bajo_minimo_articulo_sin_receta_no_crea_nada(env):
    """La harina es insumo, no una subreceta con BOM propia: nada que producir."""
    client, ids, TestSession = env
    with TestSession() as s:
        empresa_id = uuid.UUID(ids["empresa_id"])
        almacen_sucursal = Almacen(empresa_id=empresa_id, nombre="Sucursal 2", tipo="sucursal")
        s.add(almacen_sucursal)
        s.flush()
        sku_harina = s.scalar(
            select(Sku).where(Sku.articulo_id == uuid.UUID(ids["harina_id"]))
        )
        _publicar_stock_bajo_minimo(s, almacen_id=almacen_sucursal.id, sku_id=sku_harina.id)
        s.commit()

    with TestSession() as s:
        assert s.scalar(
            select(OrdenProduccion).where(
                OrdenProduccion.articulo_id == uuid.UUID(ids["harina_id"])
            )
        ) is None


def test_stock_bajo_minimo_no_duplica_con_orden_ya_abierta(env):
    client, ids, TestSession = env
    h = _token(client)
    _crear_orden(client, h, ids, idempotency_key="op-necesidad-previa")

    with TestSession() as s:
        empresa_id = uuid.UUID(ids["empresa_id"])
        almacen_sucursal = Almacen(empresa_id=empresa_id, nombre="Sucursal 3", tipo="sucursal")
        s.add(almacen_sucursal)
        s.flush()
        sku_masa = s.scalar(select(Sku).where(Sku.articulo_id == uuid.UUID(ids["masa_id"])))
        _publicar_stock_bajo_minimo(s, almacen_id=almacen_sucursal.id, sku_id=sku_masa.id)
        s.commit()

    with TestSession() as s:
        total = s.scalar(
            select(func.count())
            .select_from(OrdenProduccion)
            .where(OrdenProduccion.articulo_id == uuid.UUID(ids["masa_id"]))
        )
        assert total == 1  # la que ya estaba abierta, no una segunda


def test_stock_bajo_minimo_es_idempotente_por_dia(env):
    client, ids, TestSession = env
    with TestSession() as s:
        empresa_id = uuid.UUID(ids["empresa_id"])
        almacen_sucursal = Almacen(empresa_id=empresa_id, nombre="Sucursal 4", tipo="sucursal")
        s.add(almacen_sucursal)
        s.flush()
        sku_masa = s.scalar(select(Sku).where(Sku.articulo_id == uuid.UUID(ids["masa_id"])))
        _publicar_stock_bajo_minimo(s, almacen_id=almacen_sucursal.id, sku_id=sku_masa.id)
        s.commit()

    # Segundo reintento: no está "abierta" en el sentido de RN-PRD-007 (bien
    # podría haber cerrado), pero la misma clave de idempotencia del mismo
    # día no debe crear una segunda fila.
    with TestSession() as s:
        almacen_sucursal = s.scalar(select(Almacen).where(Almacen.nombre == "Sucursal 4"))
        sku_masa = s.scalar(select(Sku).where(Sku.articulo_id == uuid.UUID(ids["masa_id"])))
        _publicar_stock_bajo_minimo(s, almacen_id=almacen_sucursal.id, sku_id=sku_masa.id)
        s.commit()

    with TestSession() as s:
        total = s.scalar(
            select(func.count())
            .select_from(OrdenProduccion)
            .where(OrdenProduccion.articulo_id == uuid.UUID(ids["masa_id"]))
        )
        assert total == 1


def test_registrar_consumo_estado_invalido_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-5").json()["id"]
    body = _consumo_body(ids)
    assert client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=body
    ).status_code == 200
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=body)
    assert r.status_code == 409


def test_completar_sin_consumo_409(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-6").json()["id"]
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
    })
    assert r.status_code == 409


def test_idempotencia_crear_orden(env):
    client, ids, _ = env
    h = _token(client)
    r1 = _crear_orden(client, h, ids, idempotency_key="op-key-7")
    r2 = _crear_orden(client, h, ids, idempotency_key="op-key-7")
    assert r1.json()["id"] == r2.json()["id"]


def test_rol_sin_permiso_production_403(env):
    client, ids, TestSession = env
    with TestSession() as s:
        cajero = Usuario(username="cajero_test", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cajero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cajero"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol.id))
        s.commit()

    h_cajero = _token(client, "cajero_test", "222222")
    r = _crear_orden(client, h_cajero, ids, idempotency_key="op-key-8")
    assert r.status_code == 403


def test_trabajadores_disponibles_lista_activos_de_la_empresa(env):
    client, ids, _ = env
    h = _token(client)
    r = client.get("/api/v1/production/trabajadores-disponibles", headers=h)
    assert r.status_code == 200, r.text
    (trabajador,) = r.json()
    assert trabajador["id"] == ids["cocinero_id"]
    assert trabajador["cargo"] == "Cocinero"


def test_trabajadores_disponibles_filtra_por_area(env):
    client, ids, _ = env
    h = _token(client)
    vacio = client.get(
        "/api/v1/production/trabajadores-disponibles?area=Comercial", headers=h
    ).json()
    assert vacio == []
    cocina = client.get(
        "/api/v1/production/trabajadores-disponibles?area=Cocina", headers=h
    ).json()
    assert len(cocina) == 1


def test_listar_ordenes_filtra_por_estado_y_pagina(env):
    """Sin listado, la cocina solo podía ver una orden si ya sabía su id."""
    client, ids, _ = env
    h = _token(client)
    _crear_orden(client, h, ids, idempotency_key="op-list-1")
    _crear_orden(client, h, ids, idempotency_key="op-list-2")

    r = client.get("/api/v1/production/ordenes", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == 2
    assert len(r.json()["items"]) == 2

    # Recién creadas: todas en borrador, ninguna conforme.
    borrador = client.get("/api/v1/production/ordenes?estado=borrador", headers=h).json()
    assert borrador["total"] == 2
    conformes = client.get("/api/v1/production/ordenes?estado=conforme", headers=h).json()
    assert conformes["total"] == 0

    pagina = client.get("/api/v1/production/ordenes?page_size=1", headers=h).json()
    assert pagina["total"] == 2
    assert len(pagina["items"]) == 1


def test_listar_ordenes_de_un_almacen_ajeno_403(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        empresa_base = s.get(Empresa, uuid.UUID(ids["empresa_id"]))
        otra = Empresa(
            grupo_id=empresa_base.grupo_id,
            ruc="20600000009",
            razon_social="Ajena EIRL",
            domicilio_fiscal="Lima",
            tipo="operativa",
            zona_tributaria="amazonia_ley27037",
        )
        s.add(otra)
        s.flush()
        almacen = Almacen(
            empresa_id=otra.id, sucursal_id=None, nombre="Ajeno", tipo="central"
        )
        s.add(almacen)
        s.commit()
        almacen_ajeno = str(almacen.id)

    r = client.get(
        f"/api/v1/production/ordenes?almacen_id={almacen_ajeno}", headers=h
    )
    assert r.status_code == 403


# --- Lote/trazabilidad, auditoría e idempotencia (feat/produccion-lote-trazabilidad-auditoria) ---
def test_completar_conforme_con_vencimiento_genera_lote_con_esa_fecha(env):
    """Sin esto el lote nacía sin vencimiento y FEFO lo trataba como FIFO
    (RN-VNC-001) — el listener de `inventory` ya sabía leerlo, solo faltaba
    que `production` lo mandara."""
    client, ids, TestSession = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-lote-1").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": _trabajadores_body(ids),
        "fecha_vencimiento": "2026-12-31", "lote_codigo": "LOTE-PRD-001",
        "trazabilidad": {"linea": "L1", "manipulador_id": "u-123"},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fecha_vencimiento"] == "2026-12-31"
    assert body["lote_codigo"] == "LOTE-PRD-001"
    assert body["trazabilidad"] == {"linea": "L1", "manipulador_id": "u-123"}

    with TestSession() as s:
        lote = s.scalar(
            select(Lote).where(
                Lote.articulo_id == uuid.UUID(ids["masa_id"]),
                Lote.codigo == "LOTE-PRD-001",
            )
        )
        assert lote is not None
        assert lote.origen == "produccion"
        assert lote.fecha_vencimiento.isoformat() == "2026-12-31"
        assert lote.referencia == orden_id


def test_completar_conforme_sin_vencimiento_el_lote_nace_sin_el(env):
    """Sigue siendo válido no mandarlo — FEFO cae a FIFO, como siempre."""
    client, ids, TestSession = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-lote-2").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": _trabajadores_body(ids),
    })
    assert r.status_code == 200
    assert r.json()["fecha_vencimiento"] is None

    with TestSession() as s:
        lote = s.scalar(
            select(Lote).where(
                Lote.articulo_id == uuid.UUID(ids["masa_id"]), Lote.referencia == orden_id,
            )
        )
        assert lote is not None
        assert lote.fecha_vencimiento is None


def test_idempotencia_registrar_consumo(env):
    """Un reintento de red con la misma clave no duplica el consumo."""
    client, ids, TestSession = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-idem-consumo").json()["id"]
    body = _consumo_body(ids)
    body["idempotency_key"] = "consumo-key-1"

    r1 = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=body
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=body
    )
    assert r2.status_code == 200
    assert r2.json() == r1.json()

    with TestSession() as s:
        from src.modules.production.infrastructure.models import ConsumoProduccionItem
        filas = s.scalars(
            select(ConsumoProduccionItem).where(
                ConsumoProduccionItem.orden_produccion_id == uuid.UUID(orden_id)
            )
        ).all()
        assert len(filas) == 1  # no se duplicó


def test_idempotencia_completar_orden(env):
    """Un reintento de red con la misma clave no vuelve a cerrar la orden
    ni duplica el lote/asiento — devuelve la orden tal como quedó."""
    client, ids, TestSession = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-key-idem-completar").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    cuerpo = {
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": _trabajadores_body(ids),
        "idempotency_key": "completar-key-1",
    }
    r1 = client.post(
        f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json=cuerpo
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json=cuerpo
    )
    assert r2.status_code == 200
    # Comparación por valor, no por string: la primera respuesta viene del
    # objeto recién calculado en memoria y la segunda de una fila releída de
    # la base, que normaliza los decimales a la escala de la columna.
    b1, b2 = r1.json(), r2.json()
    assert b2["id"] == b1["id"] == orden_id
    assert b2["estado"] == b1["estado"] == "conforme"
    assert Decimal(b2["costo_real_unitario"]) == Decimal(b1["costo_real_unitario"])
    assert Decimal(b2["cantidad_producida"]) == Decimal(b1["cantidad_producida"])

    with TestSession() as s:
        masa = s.get(Articulo, uuid.UUID(ids["masa_id"]))
        # El costo promedio no se recalculó dos veces (seguiría en 5 si se
        # hubiera vuelto a sumar 10 unidades a 5 de costo).
        assert masa.costo_promedio == Decimal("5.0000")


def test_auditoria_registra_crear_consumo_y_completar(env):
    client, ids, TestSession = env
    h = _token(client)
    orden = _crear_orden(client, h, ids, idempotency_key="op-key-auditoria")
    orden_id = orden.json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": _trabajadores_body(ids),
    })

    with TestSession() as s:
        acciones = s.scalars(
            select(AuditLog.accion).where(
                AuditLog.entidad == "orden_produccion",
                AuditLog.entidad_id == uuid.UUID(orden_id),
            )
        ).all()
    assert set(acciones) == {"crear", "registrar_consumo", "completar"}


# --- Desecho → contabilidad (feat/produccion-desecho-a-contabilidad, ADR-100) ---
def test_completar_desechado_publica_orden_desechada_con_costo_insumos(env):
    """ADR-100: el hecho contable del desecho es el costo de los insumos ya
    consumidos, no la merma de `inventory` — el producto terminado de una
    orden desechada nunca llegó a existir como stock."""
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-desecho-1").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )

    evidencia_id = _adjuntar_evidencia(client, h, orden_id).json()["id"]

    eventos = []
    event_bus.subscribe("production.orden_desechada", eventos.append)
    eventos_no_conformidad = []
    event_bus.subscribe("production.no_conformidad_detectada", eventos_no_conformidad.append)
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_desechado", "merma_cantidad": "10",
        "merma_motivo": "contaminación",
    })
    assert r.status_code == 200, r.text

    (evento,) = eventos
    assert evento["orden_produccion_id"] == orden_id
    assert evento["almacen_id"] == ids["almacen_id"]
    assert evento["articulo_id"] == ids["masa_id"]
    # 10 de harina a 2.00 (ver `_consumo_body`): el costo de insumos, no la
    # mano de obra (que ya se reconoce aparte, como gasto de planilla).
    assert Decimal(evento["monto"]) == Decimal("20.00")
    assert evento["merma_motivo"] == "contaminación"
    # RN-PRD-015: la misma evidencia viaja también en `no_conformidad_
    # detectada`, para que el escalamiento nazca con ella sin pedirla de nuevo.
    (evento_no_conformidad,) = eventos_no_conformidad
    assert evento_no_conformidad["evidencia_id"] == evidencia_id


def test_completar_reprocesado_no_publica_orden_desechada(env):
    """Reproceso no genera merma ni asiento (RN-PRD): el insumo se corrigió,
    no se perdió."""
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-reproceso-1").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )

    eventos = []
    event_bus.subscribe("production.orden_desechada", eventos.append)
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "no_conforme_reprocesado",
    })
    assert r.status_code == 200
    assert eventos == []


# --- Costeo real (feat/produccion-costeo-real) ---
def test_consumo_sugerido_explota_la_receta_bom(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-sugerido-1").json()["id"]
    r = client.get(
        f"/api/v1/production/ordenes/{orden_id}/consumo-sugerido", headers=h
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert Decimal(body["factor"]) == Decimal("1")  # 10 planeada / 10 rendimiento
    (linea,) = body["items"]
    assert linea["articulo_id"] == ids["harina_id"]
    assert Decimal(linea["cantidad_sugerida"]) == Decimal("1")  # 1 harina * factor 1, sin merma


def test_consumo_sugerido_sin_receta_404(env):
    client, ids, TestSession = env
    h = _token(client)
    # Un almacén de producción con una orden ad-hoc sobre un artículo sin
    # receta no puede darse (crear_orden ya lo rechaza), así que se fuerza
    # el escenario escribiendo la orden directo.
    with TestSession() as s:
        orden = OrdenProduccion(
            articulo_id=uuid.UUID(ids["masa_id"]),
            almacen_id=uuid.UUID(ids["almacen_id"]),
            cantidad_planeada=Decimal(5),
            creado_por=s.scalar(select(Usuario).where(Usuario.username == "admin")).id,
            idempotency_key="op-sin-receta-forzada",
        )
        s.add(orden)
        s.commit()
        orden_id = str(orden.id)
        # Borra la receta que producía la masa: ya no hay qué explotar.
        receta = s.scalar(select(Receta).where(Receta.articulo_id == uuid.UUID(ids["masa_id"])))
        for item in s.scalars(
            select(RecetaItem).where(RecetaItem.receta_id == receta.id)
        ):
            s.delete(item)
        s.flush()
        s.delete(receta)
        s.commit()

    r = client.get(
        f"/api/v1/production/ordenes/{orden_id}/consumo-sugerido", headers=h
    )
    assert r.status_code == 409


def test_registrar_consumo_sin_costo_unitario_usa_costo_promedio(env):
    """Sin `costo_unitario` explícito, se costea al `costo_promedio` vigente
    del artículo (RN-PRD-018) en vez de que quien registra el consumo lo
    tipee sin ninguna referencia."""
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        harina = s.get(Articulo, uuid.UUID(ids["harina_id"]))
        harina.costo_promedio = Decimal("3.50")
        s.commit()

    orden_id = _crear_orden(client, h, ids, idempotency_key="op-sin-costo-1").json()["id"]
    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{"articulo_id": ids["harina_id"], "cantidad": "10"}],
        },
    )
    assert r.status_code == 200, r.text

    with TestSession() as s:
        from src.modules.production.infrastructure.models import ConsumoProduccionItem

        item = s.scalar(
            select(ConsumoProduccionItem).where(
                ConsumoProduccionItem.orden_produccion_id == uuid.UUID(orden_id)
            )
        )
        assert item.costo_unitario == Decimal("3.5000")


def test_registrar_consumo_convierte_otra_udm_de_la_misma_categoria(env):
    """RN-UDM-005: se puede teclear en gramos un insumo que se lleva en
    kilos — se guarda ya convertido a la unidad del artículo."""
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        harina = s.get(Articulo, uuid.UUID(ids["harina_id"]))
        udm_kilo = s.get(UnidadMedida, harina.unidad_medida_id)
        gramo = UnidadMedida(
            categoria_udm_id=udm_kilo.categoria_udm_id, nombre="Gramo", ratio=Decimal("0.001"),
        )
        s.add(gramo)
        s.commit()
        gramo_id = str(gramo.id)

    orden_id = _crear_orden(client, h, ids, idempotency_key="op-udm-1").json()["id"]
    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{
                "articulo_id": ids["harina_id"], "cantidad": "2000",
                "unidad_medida_id": gramo_id, "costo_unitario": "2.00",
            }],
        },
    )
    assert r.status_code == 200, r.text

    with TestSession() as s:
        from src.modules.production.infrastructure.models import ConsumoProduccionItem

        item = s.scalar(
            select(ConsumoProduccionItem).where(
                ConsumoProduccionItem.orden_produccion_id == uuid.UUID(orden_id)
            )
        )
        assert item.cantidad == Decimal("2.0000")  # 2000 g convertidos a 2 kg
        assert str(item.unidad_medida_id) == gramo_id


def test_registrar_consumo_udm_de_otra_categoria_409(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        harina = s.get(Articulo, uuid.UUID(ids["harina_id"]))
        udm_kilo = s.get(UnidadMedida, harina.unidad_medida_id)
        otra_categoria = CategoriaUdm(nombre="Volumen")
        s.add(otra_categoria)
        s.flush()
        litro = UnidadMedida(categoria_udm_id=otra_categoria.id, nombre="Litro", ratio=Decimal(1))
        s.add(litro)
        s.commit()
        litro_id = str(litro.id)
        assert udm_kilo.categoria_udm_id != otra_categoria.id

    orden_id = _crear_orden(client, h, ids, idempotency_key="op-udm-2").json()["id"]
    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{
                "articulo_id": ids["harina_id"], "cantidad": "10",
                "unidad_medida_id": litro_id, "costo_unitario": "2.00",
            }],
        },
    )
    assert r.status_code == 409


def test_completar_usa_tarifa_de_parametro_empresa_sobre_la_semilla(env):
    """RN-PRD-018/ADR-014: la tarifa la fija Gerencia en `parametro_empresa`,
    no el `.env` — la semilla solo aplica mientras nadie la aprobó."""
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        from src.shared.models.parametro_empresa import ParametroEmpresa

        admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
        s.add(ParametroEmpresa(
            empresa_id=uuid.UUID(ids["empresa_id"]), modulo="production",
            codigo="costo_hora_mano_obra", valor={"monto": "25.00"}, estado="vigente",
            propuesto_por_id=admin.id,
        ))
        s.commit()

    orden_id = _crear_orden(client, h, ids, idempotency_key="op-tarifa-1").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": _trabajadores_body(ids),
    })
    assert r.status_code == 200, r.text
    # 2 horas * 25.00 (parámetro aprobado, no la semilla de 15.00) = 50;
    # (20 insumos + 50 MO) / 10 producido = 7.
    assert Decimal(r.json()["costo_real_unitario"]) == Decimal("7.0000000000")


def test_registrar_consumo_deja_snapshot_de_costo_teorico(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        harina = s.get(Articulo, uuid.UUID(ids["harina_id"]))
        harina.costo_promedio = Decimal("2.00")
        s.commit()

    orden_id = _crear_orden(client, h, ids, idempotency_key="op-teorico-1").json()["id"]
    r = client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )
    assert r.status_code == 200
    # La receta pide 1 kg de harina por cada 10 de rendimiento; la orden
    # planea 10, factor 1: 1 kg sugerido * 2.00 de costo_promedio = 2.00.
    assert Decimal(r.json()["costo_teorico_insumos"]) == Decimal("2.0000")


def test_ver_orden_incluye_consumos_con_desviacion_de_desperdicio(env):
    client, ids, TestSession = env
    h = _token(client)
    with TestSession() as s:
        receta = s.scalar(
            select(Receta).where(Receta.articulo_id == uuid.UUID(ids["masa_id"]))
        )
        item = s.scalar(select(RecetaItem).where(RecetaItem.receta_id == receta.id))
        item.merma_pct = Decimal("10.00")
        s.commit()

    orden_id = _crear_orden(client, h, ids, idempotency_key="op-desviacion-1").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json={
            "items": [{
                "articulo_id": ids["harina_id"], "cantidad": "10", "costo_unitario": "2.00",
                "peso_desperdicio_real": "1.5",
            }],
        },
    )
    r = client.get(f"/api/v1/production/ordenes/{orden_id}", headers=h)
    assert r.status_code == 200, r.text
    (consumo,) = r.json()["consumos"]
    # Esperado por receta: 10 * 10% = 1.0; real 1.5 → desvío +0.5.
    assert Decimal(consumo["desviacion_desperdicio"]) == Decimal("0.5000")


def test_completar_conforme_no_publica_orden_desechada(env):
    client, ids, _ = env
    h = _token(client)
    orden_id = _crear_orden(client, h, ids, idempotency_key="op-conforme-sin-desecho").json()["id"]
    client.post(
        f"/api/v1/production/ordenes/{orden_id}/consumo", headers=h, json=_consumo_body(ids)
    )

    eventos = []
    event_bus.subscribe("production.orden_desechada", eventos.append)
    r = client.post(f"/api/v1/production/ordenes/{orden_id}/completar", headers=h, json={
        "resultado": "conforme", "cantidad_producida": "10",
        "trabajadores": _trabajadores_body(ids),
    })
    assert r.status_code == 200
    assert eventos == []
