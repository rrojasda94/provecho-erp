"""Tests del módulo assets: activos, kilometraje/combustible, mantenimiento
y documentos con vencimiento. SQLite en memoria + override de get_db, mismo
patrón que test_purchases.py."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.assets.application import avisos
from src.modules.assets.domain import rules
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    IncidenciaInventario,
    UnidadMedida,
)
from src.modules.reports.application import listeners as reports_listeners
from src.modules.reports.infrastructure.models import EntregaReporte, ReporteEmitido
from src.modules.users.api.deps import get_db
from src.modules.users.application import listeners as users_listeners
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared.models import Comprobante

# =============================================================================
# Dominio puro: sin BD, sin HTTP.
# =============================================================================


def test_odometro_valido_rechaza_retroceso():
    assert rules.odometro_valido(100, 50) is True
    assert rules.odometro_valido(50, 100) is False
    assert rules.odometro_valido(100, None) is True
    assert rules.odometro_valido(100, 100) is True


def test_rendimiento_km_gal_sin_distancia_o_galones_es_none():
    assert rules.rendimiento_km_gal(0, Decimal(10)) is None
    assert rules.rendimiento_km_gal(100, Decimal(0)) is None
    assert rules.rendimiento_km_gal(100, Decimal(10)) == Decimal(10)


def test_consumo_anomalo_exige_historial_minimo():
    # Una sola carga previa no alcanza para acusar de anómala a la segunda.
    assert rules.es_consumo_anomalo(Decimal(5), [Decimal(20)]) is False


def test_consumo_anomalo_por_debajo_del_promedio():
    previos = [Decimal(20), Decimal(20), Decimal(20)]
    # 20 * (1 - 0.25) = 15: 10 cae debajo del umbral por defecto (25%).
    assert rules.es_consumo_anomalo(Decimal(10), previos) is True
    # 18 se mantiene dentro de la tolerancia.
    assert rules.es_consumo_anomalo(Decimal(18), previos) is False


def test_estado_plan_por_fecha():
    hoy = date(2026, 9, 9)
    estado = rules.estado_plan(
        hoy=hoy,
        cada_dias=90,
        cada_km=None,
        dias_aviso=15,
        km_aviso=500,
        ultima_fecha=date(2026, 8, 30),
        fecha_base=hoy,
        ultimo_km=None,
        km_base=None,
        km_actual=None,
    )
    # Próxima: 2026-11-28. Hoy está a más de 15 días: al día.
    assert estado.estado == "al_dia"

    estado_proximo = rules.estado_plan(
        hoy=hoy,
        cada_dias=10,
        cada_km=None,
        dias_aviso=15,
        km_aviso=500,
        ultima_fecha=date(2026, 9, 1),
        fecha_base=hoy,
        ultimo_km=None,
        km_base=None,
        km_actual=None,
    )
    # Próxima: 2026-09-11, a 2 días — dentro de la ventana de 15.
    assert estado_proximo.estado == "proximo"

    estado_vencido = rules.estado_plan(
        hoy=hoy,
        cada_dias=5,
        cada_km=None,
        dias_aviso=15,
        km_aviso=500,
        ultima_fecha=date(2026, 9, 1),
        fecha_base=hoy,
        ultimo_km=None,
        km_base=None,
        km_actual=None,
    )
    # Próxima: 2026-09-06, ya pasada.
    assert estado_vencido.estado == "vencido"


def test_estado_plan_por_kilometraje():
    hoy = date(2026, 9, 9)
    estado = rules.estado_plan(
        hoy=hoy,
        cada_dias=None,
        cada_km=5000,
        dias_aviso=15,
        km_aviso=500,
        ultima_fecha=None,
        fecha_base=hoy,
        ultimo_km=10000,
        km_base=None,
        km_actual=14600,
    )
    # Próximo: 15000. Faltan 400 km, dentro de la ventana de 500.
    assert estado.estado == "proximo"
    assert estado.proximo_km == 15000

    vencido = rules.estado_plan(
        hoy=hoy,
        cada_dias=None,
        cada_km=5000,
        dias_aviso=15,
        km_aviso=500,
        ultima_fecha=None,
        fecha_base=hoy,
        ultimo_km=10000,
        km_base=None,
        km_actual=15200,
    )
    assert vencido.estado == "vencido"


def test_estado_documento():
    hoy = date(2026, 9, 9)
    assert (
        rules.estado_documento(
            hoy=hoy, fecha_vencimiento=date(2026, 12, 1), dias_aviso=30, renovado=False
        ).estado
        == "vigente"
    )
    assert (
        rules.estado_documento(
            hoy=hoy, fecha_vencimiento=date(2026, 9, 20), dias_aviso=30, renovado=False
        ).estado
        == "proximo"
    )
    assert (
        rules.estado_documento(
            hoy=hoy, fecha_vencimiento=date(2026, 9, 1), dias_aviso=30, renovado=False
        ).estado
        == "vencido"
    )
    assert (
        rules.estado_documento(
            hoy=hoy, fecha_vencimiento=date(2026, 9, 1), dias_aviso=30, renovado=True
        ).estado
        == "renovado"
    )


# =============================================================================
# API + tenant + integración con reports.
# =============================================================================


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(reports_listeners, "session_factory", TestSession)
    monkeypatch.setattr(users_listeners, "session_factory", TestSession)
    monkeypatch.setattr(inventory_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        almacen = s.scalar(select(Almacen).where(Almacen.empresa_id == empresa.id))
        sucursal = s.scalar(select(Sucursal).where(Sucursal.empresa_id == empresa.id))

        udm_cat = CategoriaUdm(nombre="Unidad")
        s.add(udm_cat)
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Galón", ratio=Decimal(1))
        s.add(udm)
        s.flush()
        combustible = Articulo(
            empresa_id=empresa.id,
            id_interno="SRV001",
            nombre="Combustible",
            unidad_medida_id=udm.id,
            tipo="servicio",
        )
        s.add(combustible)
        s.flush()

        repuesto = Articulo(
            empresa_id=empresa.id,
            id_interno="REP001",
            nombre="Filtro de aceite",
            unidad_medida_id=udm.id,
            tipo="repuesto",
        )
        s.add(repuesto)
        s.flush()

        # Un usuario sin ningún permiso `assets.*` (cocinero) para el 403.
        cocinero = Usuario(username="cocinero_assets", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(cocinero)
        s.flush()
        rol_cocinero = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
        s.add(UsuarioRol(usuario_id=cocinero.id, rol_id=rol_cocinero.id))
        s.add(UsuarioSucursal(usuario_id=cocinero.id, sucursal_id=sucursal.id))

        ids.update(
            empresa_id=str(empresa.id),
            almacen_id=str(almacen.id),
            articulo_combustible_id=str(combustible.id),
            articulo_repuesto_id=str(repuesto.id),
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


def _crear_proveedor(client, headers, ids):
    body = {
        "empresa_id": ids["empresa_id"],
        "tipo": "juridico",
        "condicion_pago": "contado",
        "razon_social": "Grifo Tarapoto SAC",
        "ruc": "20222222222",
        "clasificacion": "regular",
    }
    return client.post("/api/v1/purchases/proveedores", headers=headers, json=body)


def _comprobante_de_grifo(
    client, h, ids, *, key: str, correlativo: int, monto: str = "120.00"
) -> str:
    """Un comprobante `recibido` real, vía compra directa con el artículo
    servicio, igual que haría Compras al registrar el ticket del grifo.

    `correlativo` tiene que ser distinto en cada llamada dentro del mismo
    test: dos tickets del mismo proveedor con la misma serie+correlativo
    violan `uq_comprobante_recibido` (RN-CPP-001), aunque sean cargas de
    combustible distintas.
    """
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    body = {
        "proveedor_id": proveedor_id,
        "almacen_destino_id": ids["almacen_id"],
        "idempotency_key": key,
        "items": [
            {
                "articulo_id": ids["articulo_combustible_id"],
                "cantidad": "1",
                "costo_unitario": monto,
            }
        ],
        "comprobante": {
            "idempotency_key": f"{key}-comp",
            "tipo": "boleta",
            "serie": "B001",
            "correlativo": correlativo,
            "sustento": "efectivo",
        },
    }
    r = client.post("/api/v1/purchases/compras-directas", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _crear_vehiculo(client, h, ids, *, placa="ABC-123", km=10000):
    body = {
        "tipo": "vehiculo",
        "id_interno": "V0001",
        "nombre": "Moto de reparto",
        "placa": placa,
        "tipo_vehiculo": "moto",
        "tenencia": "propio",
        "kilometraje_inicial": km,
    }
    r = client.post("/api/v1/assets/activos", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_activo_equipamiento(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0001", "nombre": "Horno pizzero"},
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "operativo"
    assert r.json()["vehiculo"] is None


def test_crear_activo_vehiculo_sin_placa_falla(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "vehiculo", "id_interno": "V0002", "nombre": "Sin placa"},
    )
    assert r.status_code == 409


def test_crear_activo_vehiculo_ok(env):
    client, ids, _ = env
    h = _token(client)
    activo = _crear_vehiculo(client, h, ids)
    assert activo["vehiculo"]["placa"] == "ABC-123"
    assert activo["vehiculo"]["kilometraje_actual"] == 10000


def test_activo_de_otra_empresa_responde_404(env):
    client, ids, TestSession = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0002", "nombre": "Congeladora"},
    ).json()

    with TestSession() as s:
        from src.modules.assets.infrastructure.models import Activo
        from src.modules.users.infrastructure.models import Grupo

        otra_empresa = Empresa(
            grupo_id=s.scalar(select(Grupo)).id,
            razon_social="Otra EIRL",
            ruc="20999999999",
            domicilio_fiscal="Jr. Y 1",
            tipo="operativa",
        )
        s.add(otra_empresa)
        s.flush()
        fila = s.get(Activo, uuid.UUID(activo["id"]))
        fila.empresa_id = otra_empresa.id
        s.commit()

    r = client.get(f"/api/v1/assets/activos/{activo['id']}", headers=h)
    # Mismo criterio que `purchases.exigir_proveedor`/`exigir_orden_compra`:
    # `Tenant.exigir_empresa` levanta `FueraDeAlcance` → 403, no 404.
    assert r.status_code == 403


def test_rol_sin_permiso_assets_403(env):
    client, ids, _ = env
    h = _token(client, username="cocinero_assets", pin="111111")
    r = client.get("/api/v1/assets/activos", headers=h)
    assert r.status_code == 403


def test_registrar_lectura_odometro_rechaza_retroceso(env):
    client, ids, _ = env
    h = _token(client)
    activo = _crear_vehiculo(client, h, ids, km=5000)
    r = client.post(
        f"/api/v1/assets/activos/{activo['id']}/lecturas-odometro",
        headers=h,
        json={"km": 4000, "fecha": str(date.today())},
    )
    assert r.status_code == 409


def test_registrar_carga_combustible_calcula_rendimiento(env):
    client, ids, _ = env
    h = _token(client)
    activo = _crear_vehiculo(client, h, ids, placa="XYZ-001", km=1000)

    comp1 = _comprobante_de_grifo(client, h, ids, key="fuel-key-1", correlativo=1)
    r1 = client.post(
        f"/api/v1/assets/activos/{activo['id']}/cargas-combustible",
        headers=h,
        json={
            "comprobante_id": comp1,
            "fecha": str(date.today()),
            "galones": "5",
            "monto": "60.00",
            "km_odometro": 1000,
        },
    )
    assert r1.status_code == 201
    assert r1.json()["rendimiento_km_gal"] is None  # primera carga, sin distancia previa

    comp2 = _comprobante_de_grifo(client, h, ids, key="fuel-key-2", correlativo=2)
    r2 = client.post(
        f"/api/v1/assets/activos/{activo['id']}/cargas-combustible",
        headers=h,
        json={
            "comprobante_id": comp2,
            "fecha": str(date.today()),
            "galones": "5",
            "monto": "60.00",
            "km_odometro": 1100,
        },
    )
    assert r2.status_code == 201
    assert r2.json()["km_recorridos"] == 100
    assert Decimal(r2.json()["rendimiento_km_gal"]) == Decimal("20.00")

    ver = client.get(f"/api/v1/assets/activos/{activo['id']}", headers=h)
    assert ver.json()["vehiculo"]["kilometraje_actual"] == 1100


def test_carga_combustible_con_comprobante_ya_usado_409(env):
    client, ids, _ = env
    h = _token(client)
    activo = _crear_vehiculo(client, h, ids, placa="XYZ-002", km=1000)
    comp = _comprobante_de_grifo(client, h, ids, key="fuel-reuso", correlativo=3)
    body = {
        "comprobante_id": comp,
        "fecha": str(date.today()),
        "galones": "5",
        "monto": "60.00",
        "km_odometro": 1000,
    }
    r1 = client.post(
        f"/api/v1/assets/activos/{activo['id']}/cargas-combustible", headers=h, json=body
    )
    assert r1.status_code == 201
    body["km_odometro"] = 1050
    r2 = client.post(
        f"/api/v1/assets/activos/{activo['id']}/cargas-combustible", headers=h, json=body
    )
    assert r2.status_code == 409


def test_carga_combustible_con_comprobante_emitido_404(env, _engine_de_prueba):
    """RN-VEH-006: la carga se sustenta con lo que la empresa **recibió**, no
    con algo que emitió — un comprobante `emitido` no sirve."""
    client, ids, TestSession = env
    h = _token(client)
    activo = _crear_vehiculo(client, h, ids, placa="XYZ-003", km=1000)
    with TestSession() as s:
        emitido = Comprobante(
            empresa_id=uuid.UUID(ids["empresa_id"]),
            direccion="emitido",
            tipo="boleta",
            serie="B001",
            correlativo=555,
            sustento="efectivo",
            idempotency_key="emitido-para-assets",
        )
        s.add(emitido)
        s.commit()
        comp_id = str(emitido.id)

    r = client.post(
        f"/api/v1/assets/activos/{activo['id']}/cargas-combustible",
        headers=h,
        json={
            "comprobante_id": comp_id,
            "fecha": str(date.today()),
            "galones": "5",
            "monto": "60.00",
            "km_odometro": 1000,
        },
    )
    assert r.status_code == 404


def test_realizar_orden_actualiza_plan_y_limpia_avisos(env):
    client, ids, TestSession = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0003", "nombre": "Freidora"},
    ).json()

    plan = client.post(
        "/api/v1/assets/planes",
        headers=h,
        json={
            "activo_id": activo["id"],
            "nombre": "Mantenimiento freidora",
            "cada_dias": 30,
            "dias_aviso": 5,
        },
    ).json()

    # Simula que el último mantenimiento fue hace 40 días: con cada_dias=30
    # el plan ya está vencido, algo que la API de alta no puede producir por
    # sí sola (siempre parte de "recién creado").
    from src.modules.assets.infrastructure.models import PlanMantenimiento

    with TestSession() as s:
        fila = s.get(PlanMantenimiento, uuid.UUID(plan["id"]))
        fila.ultima_fecha = date.today() - timedelta(days=40)
        s.commit()

    vencido = next(
        p for p in client.get("/api/v1/assets/planes", headers=h).json() if p["id"] == plan["id"]
    )
    assert vencido["estado"] == "vencido"

    orden = client.post(
        "/api/v1/assets/ordenes-mantenimiento",
        headers=h,
        json={"activo_id": activo["id"], "tipo": "programado", "plan_id": plan["id"]},
    ).json()
    assert orden["estado"] == "programada"

    iniciar = client.post(f"/api/v1/assets/ordenes-mantenimiento/{orden['id']}/iniciar", headers=h)
    assert iniciar.json()["estado"] == "en_curso"
    assert client.get(f"/api/v1/assets/activos/{activo['id']}", headers=h).json()["estado"] == (
        "en_mantenimiento"
    )

    realizar = client.post(
        f"/api/v1/assets/ordenes-mantenimiento/{orden['id']}/realizar",
        headers=h,
        json={"fecha_realizada": str(date.today())},
    )
    assert realizar.json()["estado"] == "realizada"
    assert client.get(f"/api/v1/assets/activos/{activo['id']}", headers=h).json()["estado"] == (
        "operativo"
    )

    plan_actualizado = client.get("/api/v1/assets/planes", headers=h).json()
    fila = next(p for p in plan_actualizado if p["id"] == plan["id"])
    assert fila["ultima_fecha"] == str(date.today())
    # El ciclo se cerró hoy: la próxima cae dentro de 30 días, fuera de la
    # ventana de aviso de 5 — vuelve a estar al día.
    assert fila["estado"] == "al_dia"


def test_crear_documento_y_renovar_encadena(env):
    client, ids, _ = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0004", "nombre": "Extintor"},
    ).json()

    doc = client.post(
        "/api/v1/assets/documentos",
        headers=h,
        json={
            "sujeto_tipo": "activo",
            "sujeto_id": activo["id"],
            "tipo_documento": "otro",
            "fecha_vencimiento": str(date.today() + timedelta(days=5)),
            "dias_aviso": 30,
        },
    ).json()
    assert doc["estado"] == "proximo"

    renovado = client.post(
        f"/api/v1/assets/documentos/{doc['id']}/renovar",
        headers=h,
        json={"fecha_vencimiento": str(date.today() + timedelta(days=365))},
    )
    assert renovado.status_code == 201
    assert renovado.json()["estado"] == "vigente"

    original = client.get(f"/api/v1/assets/documentos/{doc['id']}", headers=h).json()
    assert original["renovado_por_id"] == renovado.json()["id"]
    assert original["estado"] == "renovado"

    # Ya renovado: renovarlo otra vez es conflicto.
    otra_vez = client.post(
        f"/api/v1/assets/documentos/{doc['id']}/renovar",
        headers=h,
        json={"fecha_vencimiento": str(date.today() + timedelta(days=400))},
    )
    assert otra_vez.status_code == 409


def test_barrido_publica_una_sola_vez_por_ventana(env):
    client, ids, TestSession = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0005", "nombre": "Cámara de frío"},
    ).json()
    client.post(
        "/api/v1/assets/documentos",
        headers=h,
        json={
            "sujeto_tipo": "activo",
            "sujeto_id": activo["id"],
            "tipo_documento": "otro",
            "fecha_vencimiento": str(date.today() + timedelta(days=1)),
            "dias_aviso": 30,
        },
    )

    with TestSession() as s:
        publicados_1 = avisos.barrer(s)
        s.commit()
    with TestSession() as s:
        publicados_2 = avisos.barrer(s)
        s.commit()

    assert publicados_1["documento_por_vencer"] == 1
    # Segunda corrida el mismo día: ya se avisó, no se repite.
    assert publicados_2["documento_por_vencer"] == 0

    with TestSession() as s:
        emitidos = list(
            s.scalars(
                select(ReporteEmitido).where(
                    ReporteEmitido.codigo_emision == "assets.documento_por_vencer"
                )
            )
        )
        assert len(emitidos) == 1
        entregas = list(
            s.scalars(
                select(EntregaReporte).where(EntregaReporte.reporte_emitido_id == emitidos[0].id)
            )
        )
        assert len(entregas) > 0  # gerencia/contabilidad/rrhh sembrados como área


# =============================================================================
# Repuestos: compatibilidad y consumo en la orden de mantenimiento.
# =============================================================================


def test_repuesto_compatible_alta_listado_y_baja(env):
    client, ids, _ = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0006", "nombre": "Batidora"},
    ).json()

    alta = client.post(
        f"/api/v1/assets/activos/{activo['id']}/repuestos-compatibles",
        headers=h,
        json={"articulo_id": ids["articulo_repuesto_id"], "notas": "cambiar cada 6 meses"},
    )
    assert alta.status_code == 201
    repuesto_id = alta.json()["id"]

    duplicado = client.post(
        f"/api/v1/assets/activos/{activo['id']}/repuestos-compatibles",
        headers=h,
        json={"articulo_id": ids["articulo_repuesto_id"]},
    )
    assert duplicado.status_code == 409

    listado = client.get(
        f"/api/v1/assets/activos/{activo['id']}/repuestos-compatibles", headers=h
    )
    assert len(listado.json()) == 1

    baja = client.delete(
        f"/api/v1/assets/activos/{activo['id']}/repuestos-compatibles/{repuesto_id}", headers=h
    )
    assert baja.status_code == 204
    assert (
        client.get(
            f"/api/v1/assets/activos/{activo['id']}/repuestos-compatibles", headers=h
        ).json()
        == []
    )


def test_realizar_orden_con_repuestos_descuenta_stock_via_evento(env):
    client, ids, TestSession = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0007", "nombre": "Licuadora"},
    ).json()
    orden = client.post(
        "/api/v1/assets/ordenes-mantenimiento",
        headers=h,
        json={"activo_id": activo["id"], "tipo": "adelantado", "motivo_adelanto": "desperfecto"},
    ).json()

    realizar = client.post(
        f"/api/v1/assets/ordenes-mantenimiento/{orden['id']}/realizar",
        headers=h,
        json={
            "fecha_realizada": str(date.today()),
            "almacen_id": ids["almacen_id"],
            "repuestos": [{"articulo_id": ids["articulo_repuesto_id"], "cantidad": "2"}],
        },
    )
    assert realizar.status_code == 200, realizar.text
    cuerpo = realizar.json()
    assert cuerpo["estado"] == "realizada"
    assert len(cuerpo["repuestos"]) == 1
    assert cuerpo["repuestos"][0]["nombre_articulo"] == "Filtro de aceite"
    assert Decimal(cuerpo["repuestos"][0]["cantidad"]) == Decimal("2")

    # El repuesto no tiene SKU activo (no se dio de alta uno en el test): el
    # listener de `inventory` deja constancia en vez de romper la orden —
    # prueba de que el evento `assets.repuesto_consumido` sí llegó.
    with TestSession() as s:
        incidencias = list(
            s.scalars(
                select(IncidenciaInventario).where(
                    IncidenciaInventario.referencia == orden["id"]
                )
            )
        )
        assert len(incidencias) == 1
        assert incidencias[0].tipo == "sin_sku"


def test_realizar_orden_con_repuestos_sin_almacen_falla(env):
    client, ids, _ = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0008", "nombre": "Sanguchera"},
    ).json()
    orden = client.post(
        "/api/v1/assets/ordenes-mantenimiento",
        headers=h,
        json={"activo_id": activo["id"], "tipo": "adelantado", "motivo_adelanto": "desperfecto"},
    ).json()

    r = client.post(
        f"/api/v1/assets/ordenes-mantenimiento/{orden['id']}/realizar",
        headers=h,
        json={
            "fecha_realizada": str(date.today()),
            "repuestos": [{"articulo_id": ids["articulo_repuesto_id"], "cantidad": "1"}],
        },
    )
    assert r.status_code == 409


def test_realizar_orden_con_articulo_que_no_es_repuesto_falla(env):
    client, ids, _ = env
    h = _token(client)
    activo = client.post(
        "/api/v1/assets/activos",
        headers=h,
        json={"tipo": "equipamiento", "id_interno": "EQ0009", "nombre": "Vitrina"},
    ).json()
    orden = client.post(
        "/api/v1/assets/ordenes-mantenimiento",
        headers=h,
        json={"activo_id": activo["id"], "tipo": "adelantado", "motivo_adelanto": "desperfecto"},
    ).json()

    r = client.post(
        f"/api/v1/assets/ordenes-mantenimiento/{orden['id']}/realizar",
        headers=h,
        json={
            "fecha_realizada": str(date.today()),
            "almacen_id": ids["almacen_id"],
            # El artículo "Combustible" es tipo=servicio, no repuesto.
            "repuestos": [{"articulo_id": ids["articulo_combustible_id"], "cantidad": "1"}],
        },
    )
    assert r.status_code == 409
