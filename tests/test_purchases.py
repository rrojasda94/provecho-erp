"""Tests del slice purchases core: proveedores y ciclo de OC (crear → emitir
→ recibir → anular). SQLite en memoria + override de get_db, mismo patrón
que test_inventory.py.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Sku,
    UnidadMedida,
)
from src.modules.purchases.application import proveedores as proveedores_uc
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Persona,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared import fechas


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(listeners, "session_factory", TestSession)

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
        art = Articulo(
            empresa_id=empresa.id, id_interno="H001", nombre="Harina",
            unidad_medida_id=None, tipo="insumo",
        )
        s.add_all([udm, almacen])
        s.flush()
        art.unidad_medida_id = udm.id
        s.add(art)
        s.flush()
        sku = Sku(articulo_id=art.id, codigo="SKU-HARINA")
        s.add(sku)
        s.flush()

        comprador = Usuario(username="comprador1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(comprador)
        s.flush()
        rol_comprador = s.scalar(select(Rol).where(Rol.nombre == "comprador"))
        s.add(UsuarioRol(usuario_id=comprador.id, rol_id=rol_comprador.id))
        # Sin sucursal el JWT sale sin `empresa_id` y todo responde 403 (ADR-004).
        s.add(
            UsuarioSucursal(
                usuario_id=comprador.id, sucursal_id=s.scalar(select(Sucursal)).id
            )
        )

        persona = Persona(
            nombres="Juan", apellidos="Perez", tipo_documento="dni",
            numero_documento="10000009",
        )
        s.add(persona)
        s.flush()

        ids.update(
            empresa_id=str(empresa.id), almacen_id=str(almacen.id),
            articulo_id=str(art.id), sku_id=str(sku.id), persona_id=str(persona.id),
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


def _crear_proveedor(client, headers, ids, **overrides):
    body = {
        "empresa_id": ids["empresa_id"],
        "tipo": "juridico",
        "condicion_pago": "contado",
        "razon_social": "Molinera SAC",
        "ruc": "20111111111",
        "clasificacion": "preferente",
    }
    body.update(overrides)
    return client.post("/api/v1/purchases/proveedores", headers=headers, json=body)


def test_crear_proveedor_juridico(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_proveedor(client, h, ids)
    assert r.status_code == 201
    assert r.json()["ruc"] == "20111111111"


def test_crear_proveedor_juridico_consulta_factiliza_para_la_razon_social(env, monkeypatch):
    client, ids, _ = env
    monkeypatch.setattr(
        proveedores_uc, "razon_social_desde_ruc", lambda ruc, fallback: "SERVICIOS RENTAURANT S.A.C"
    )
    h = _token(client)
    r = _crear_proveedor(client, h, ids, ruc="20610077782")
    assert r.status_code == 201
    assert r.json()["razon_social"] == "SERVICIOS RENTAURANT S.A.C"


def test_crear_proveedor_juridico_sin_ruc_409(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_proveedor(client, h, ids, ruc=None, razon_social=None)
    assert r.status_code == 409


def test_crear_proveedor_natural_requiere_persona(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/purchases/proveedores", headers=h, json={
        "empresa_id": ids["empresa_id"], "tipo": "natural", "condicion_pago": "contado",
        "persona_id": ids["persona_id"],
    })
    assert r.status_code == 201
    assert r.json()["tipo"] == "natural"
    # Antes no viajaba: un proveedor natural no tenía forma de mostrarse
    # por nombre en un listado (se resuelve contra `persona`, RN-GEN-007).
    assert r.json()["persona_id"] == ids["persona_id"]


def test_crear_proveedor_natural_sin_persona_id_409(env):
    client, ids, _ = env
    h = _token(client)
    r = client.post("/api/v1/purchases/proveedores", headers=h, json={
        "empresa_id": ids["empresa_id"], "tipo": "natural", "condicion_pago": "contado",
    })
    assert r.status_code == 409


def test_credito_sin_plazo_409(env):
    client, ids, _ = env
    h = _token(client)
    r = _crear_proveedor(client, h, ids, condicion_pago="credito")
    assert r.status_code == 409


# --- Corrección de un proveedor ya dado de alta -----------------------------
def test_editar_proveedor_corrige_ruc_y_razon_social(env, monkeypatch):
    """El caso que motivó el cambio: un RUC mal tecleado llega hasta la
    factura electrónica y hasta ahora solo se corregía tocando la base."""
    client, ids, _ = env
    monkeypatch.setattr(
        proveedores_uc, "razon_social_desde_ruc", lambda ruc, fallback: fallback
    )
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    r = client.patch(
        f"/api/v1/purchases/proveedores/{proveedor_id}",
        headers=h,
        json={"ruc": "20222222222", "razon_social": "Molinera del Sur SAC"},
    )
    assert r.status_code == 200
    assert r.json()["ruc"] == "20222222222"
    assert r.json()["razon_social"] == "Molinera del Sur SAC"


def test_editar_proveedor_natural_no_admite_razon_social(env):
    """Los datos de un natural viven en su persona (RN-GEN-007); dejarle
    razón social propia sería crear la segunda fuente que esa regla evita."""
    client, ids, _ = env
    h = _token(client)
    proveedor_id = client.post(
        "/api/v1/purchases/proveedores",
        headers=h,
        json={
            "empresa_id": ids["empresa_id"],
            "tipo": "natural",
            "condicion_pago": "contado",
            "persona_id": ids["persona_id"],
        },
    ).json()["id"]

    r = client.patch(
        f"/api/v1/purchases/proveedores/{proveedor_id}",
        headers=h,
        json={"razon_social": "Inventada SAC"},
    )
    assert r.status_code == 409
    assert "persona" in r.json()["detail"]


def test_editar_proveedor_a_credito_sin_plazo_409(env):
    """Misma regla que el alta: 'credito' sin plazo deja a accounting sin
    fecha de vencimiento que calcular."""
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    r = client.patch(
        f"/api/v1/purchases/proveedores/{proveedor_id}",
        headers=h,
        json={"condicion_pago": "credito"},
    )
    assert r.status_code == 409


def test_editar_proveedor_clasificacion_invalida_422(env):
    """La columna es un Enum con CHECK: sin el `Literal` del schema esto
    moría en el flush con un 500 en vez de un 422 que se lee."""
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    r = client.patch(
        f"/api/v1/purchases/proveedores/{proveedor_id}",
        headers=h,
        json={"clasificacion": "vip"},
    )
    assert r.status_code == 422


def _crear_oc(client, headers, ids, proveedor_id, idempotency_key="oc-key-1", costo="10.00"):
    return client.post("/api/v1/purchases/ordenes-compra", headers=headers, json={
        "proveedor_id": proveedor_id,
        "almacen_destino_id": ids["almacen_id"],
        "idempotency_key": idempotency_key,
        "items": [{"articulo_id": ids["articulo_id"], "cantidad": "100", "costo_unitario": costo}],
    })


def test_flujo_oc_completo_actualiza_stock_y_costo(env):
    client, ids, TestSession = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    oc = _crear_oc(client, h, ids, proveedor_id)
    assert oc.status_code == 201
    oc_id = oc.json()["id"]
    assert oc.json()["estado"] == "borrador"
    assert Decimal(oc.json()["total"]) == Decimal("1000.00")

    emit = client.post(f"/api/v1/purchases/ordenes-compra/{oc_id}/emitir", headers=h)
    assert emit.status_code == 200
    assert emit.json()["estado"] == "emitida"

    # Comprometer plata con un proveedor deja rastro (ADR-031).
    from src.shared.models import AuditLog
    with TestSession() as s:
        rastro = s.scalar(
            select(AuditLog).where(AuditLog.entidad_id == uuid.UUID(oc_id))
        )
    assert rastro.accion == "emitir"
    assert rastro.datos_despues["total"] == "1000.00"

    # ítem id: solo hay uno, lo leemos de la BD directo (no hay GET de items).
    from src.modules.purchases.infrastructure.models import OrdenCompraItem
    with TestSession() as s:
        item = s.scalar(
            select(OrdenCompraItem).where(
                OrdenCompraItem.orden_compra_id == uuid.UUID(oc_id)
            )
        )
        item_id = str(item.id)

    recepcion = client.post(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/recepciones", headers=h, json={
            "idempotency_key": "recep-key-1",
            "items": [{"orden_compra_item_id": item_id, "cantidad_recibida": "100"}],
        },
    )
    assert recepcion.status_code == 201

    ver = client.get(f"/api/v1/purchases/ordenes-compra/{oc_id}", headers=h)
    assert ver.json()["estado"] == "recibida"

    stock = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['almacen_id']}", headers=h
    ).json()["items"]
    assert Decimal(stock[0]["cantidad"]) == Decimal("100")

    with TestSession() as s:
        art = s.get(Articulo, uuid.UUID(ids["articulo_id"]))
        assert art.costo_promedio == Decimal("10.0000")


def test_la_recepcion_conserva_el_lote_que_declaro_el_proveedor(env):
    """El dato viajaba solo en el evento: si el listener de `inventory`
    fallaba, no quedaba dónde leerlo para reprocesar (RN-VNC-002)."""
    client, ids, TestSession = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_id = _crear_oc(
        client, h, ids, proveedor_id, idempotency_key="oc-key-lote"
    ).json()["id"]
    client.post(f"/api/v1/purchases/ordenes-compra/{oc_id}/emitir", headers=h)

    from src.modules.purchases.infrastructure.models import (
        OrdenCompraItem,
        RecepcionItem,
    )
    with TestSession() as s:
        item_id = str(
            s.scalar(
                select(OrdenCompraItem).where(
                    OrdenCompraItem.orden_compra_id == uuid.UUID(oc_id)
                )
            ).id
        )

    r = client.post(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/recepciones", headers=h, json={
            "idempotency_key": "recep-key-lote",
            "items": [{
                "orden_compra_item_id": item_id, "cantidad_recibida": "100",
                "lote_codigo": "LT-2026-08", "fecha_vencimiento": "2026-12-31",
            }],
        },
    )
    assert r.status_code == 201, r.text

    with TestSession() as s:
        linea = s.scalar(select(RecepcionItem))
    assert linea.lote_codigo == "LT-2026-08"
    assert linea.fecha_vencimiento.isoformat() == "2026-12-31"


def test_recibir_mas_de_lo_ordenado_409(env):
    client, ids, TestSession = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_id = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-key-2").json()["id"]
    client.post(f"/api/v1/purchases/ordenes-compra/{oc_id}/emitir", headers=h)

    from src.modules.purchases.infrastructure.models import OrdenCompraItem
    with TestSession() as s:
        item = s.scalar(
            select(OrdenCompraItem).where(
                OrdenCompraItem.orden_compra_id == uuid.UUID(oc_id)
            )
        )
        item_id = str(item.id)

    r = client.post(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/recepciones", headers=h, json={
            "idempotency_key": "recep-key-2",
            "items": [{"orden_compra_item_id": item_id, "cantidad_recibida": "999"}],
        },
    )
    assert r.status_code == 409


def test_emitir_oc_sobre_umbral_sin_permiso_aprobar_409(env):
    client, ids, _ = env
    h_admin = _token(client)
    h_comprador = _token(client, "comprador1", "111111")
    proveedor_id = _crear_proveedor(client, h_admin, ids).json()["id"]
    # 100 * 50 = 5000, sobre el umbral semilla (2000).
    oc = _crear_oc(
        client, h_comprador, ids, proveedor_id, idempotency_key="oc-key-3", costo="50.00"
    )
    oc_id = oc.json()["id"]
    r = client.post(f"/api/v1/purchases/ordenes-compra/{oc_id}/emitir", headers=h_comprador)
    assert r.status_code == 409
    # admin tiene "*" (incluye purchases.aprobar) y sí puede.
    r2 = client.post(f"/api/v1/purchases/ordenes-compra/{oc_id}/emitir", headers=h_admin)
    assert r2.status_code == 200


def test_parametro_aprobado_sube_el_umbral_de_oc_de_la_empresa(env):
    """Con un `parametro_empresa` aprobado que sube el umbral para esta
    empresa, una OC que antes exigía `purchases.aprobar` (sobre el umbral
    semilla S/2000) ya no lo exige. Proponer no basta: hace falta que
    Gerencia apruebe (RN-GER-009)."""
    client, ids, _ = env
    h_admin = _token(client)
    h_comprador = _token(client, "comprador1", "111111")

    r = client.post(
        "/api/v1/parametros",
        headers=h_admin,
        json={
            "empresa_id": ids["empresa_id"],
            "modulo": "purchases",
            "codigo": "oc_umbral",
            "valor": {"monto": "10000", "divisa": "PEN"},
        },
    )
    assert r.status_code == 201
    aprobacion = client.post(
        f"/api/v1/parametros/{r.json()['id']}/aprobar", headers=h_admin, json={}
    )
    assert aprobacion.status_code == 200

    proveedor_id = _crear_proveedor(client, h_admin, ids).json()["id"]
    # 100 * 50 = 5000: bajo el umbral semilla (2000) hubiera exigido aprobar,
    # pero bajo el umbral configurado (10000) ya no.
    oc = _crear_oc(
        client, h_comprador, ids, proveedor_id, idempotency_key="oc-key-regla", costo="50.00"
    )
    r2 = client.post(
        f"/api/v1/purchases/ordenes-compra/{oc.json()['id']}/emitir", headers=h_comprador
    )
    assert r2.status_code == 200


def test_anular_oc_borrador_ok_y_recibida_409(env):
    client, ids, TestSession = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    oc1_id = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-key-4").json()["id"]
    r = client.post(f"/api/v1/purchases/ordenes-compra/{oc1_id}/anular", headers=h)
    assert r.status_code == 200
    assert r.json()["estado"] == "anulada"

    oc2_id = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-key-5").json()["id"]
    client.post(f"/api/v1/purchases/ordenes-compra/{oc2_id}/emitir", headers=h)
    from src.modules.purchases.infrastructure.models import OrdenCompraItem
    with TestSession() as s:
        item = s.scalar(
            select(OrdenCompraItem).where(
                OrdenCompraItem.orden_compra_id == uuid.UUID(oc2_id)
            )
        )
        item_id = str(item.id)
    client.post(
        f"/api/v1/purchases/ordenes-compra/{oc2_id}/recepciones", headers=h, json={
            "idempotency_key": "recep-key-5",
            "items": [{"orden_compra_item_id": item_id, "cantidad_recibida": "100"}],
        },
    )
    r2 = client.post(f"/api/v1/purchases/ordenes-compra/{oc2_id}/anular", headers=h)
    assert r2.status_code == 409


def test_crear_oc_tipo_activo_409(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    r = client.post("/api/v1/purchases/ordenes-compra", headers=h, json={
        "proveedor_id": proveedor_id,
        "almacen_destino_id": ids["almacen_id"],
        "idempotency_key": "oc-key-6",
        "tipo": "activo",
        "items": [{"articulo_id": ids["articulo_id"], "cantidad": "1", "costo_unitario": "500"}],
    })
    assert r.status_code == 409


def test_idempotencia_crear_oc(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    r1 = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-key-7")
    r2 = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-key-7")
    assert r1.json()["id"] == r2.json()["id"]


def test_editar_orden_compra_en_borrador_reemplaza_items_y_recalcula_total(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-edit-1")
    oc_id = oc.json()["id"]
    assert Decimal(oc.json()["total"]) == Decimal("1000.00")

    r = client.patch(
        f"/api/v1/purchases/ordenes-compra/{oc_id}",
        headers=h,
        json={
            "items": [
                {"articulo_id": ids["articulo_id"], "cantidad": "50", "costo_unitario": "20.00"}
            ]
        },
    )
    assert r.status_code == 200
    assert Decimal(r.json()["total"]) == Decimal("1000.00")  # 50 * 20
    assert len(r.json()["items"]) == 1
    assert Decimal(r.json()["items"][0]["cantidad"]) == Decimal("50")


def test_editar_orden_compra_fuera_de_borrador_falla(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-edit-2")
    oc_id = oc.json()["id"]
    client.post(f"/api/v1/purchases/ordenes-compra/{oc_id}/emitir", headers=h)

    r = client.patch(
        f"/api/v1/purchases/ordenes-compra/{oc_id}",
        headers=h,
        json={
            "items": [
                {"articulo_id": ids["articulo_id"], "cantidad": "1", "costo_unitario": "1.00"}
            ]
        },
    )
    assert r.status_code == 409


def test_editar_orden_compra_sin_items_falla(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc = _crear_oc(client, h, ids, proveedor_id, idempotency_key="oc-edit-3")
    oc_id = oc.json()["id"]

    r = client.patch(
        f"/api/v1/purchases/ordenes-compra/{oc_id}", headers=h, json={"items": []}
    )
    assert r.status_code == 422


def _compra_directa_body(ids, proveedor_id, idempotency_key="cd-key-1"):
    return {
        "proveedor_id": proveedor_id,
        "almacen_destino_id": ids["almacen_id"],
        "idempotency_key": idempotency_key,
        "items": [{"articulo_id": ids["articulo_id"], "cantidad": "10", "costo_unitario": "5.00"}],
        "comprobante": {
            "idempotency_key": f"{idempotency_key}-comp",
            "tipo": "boleta",
            "serie": "B001",
            "correlativo": 1,
            "sustento": "efectivo",
        },
    }


def test_registrar_compra_directa_crea_oc_recibida_y_conforme(env):
    client, ids, TestSession = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    r = client.post(
        "/api/v1/purchases/compras-directas", headers=h,
        json=_compra_directa_body(ids, proveedor_id),
    )
    assert r.status_code == 201
    assert r.json()["direccion"] == "recibido"
    comprobante_id = r.json()["id"]
    orden_id = r.json()["compra_id"]

    ver = client.get(f"/api/v1/purchases/ordenes-compra/{orden_id}", headers=h)
    assert ver.json()["estado"] == "recibida"
    assert ver.json()["origen"] == "directa"

    from src.shared.models import Comprobante
    with TestSession() as s:
        comprobante = s.get(Comprobante, uuid.UUID(comprobante_id))
        assert comprobante.compra_id == uuid.UUID(orden_id)


def test_registrar_compra_directa_publica_evento_compra_recibida_con_contrato_existente(env):
    """El evento que consume `inventory` para entrar stock es el mismo que
    el de una recepción normal — la compra directa entra stock sin tocar
    ese listener."""
    client, ids, TestSession = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    client.post(
        "/api/v1/purchases/compras-directas", headers=h,
        json=_compra_directa_body(ids, proveedor_id, idempotency_key="cd-key-2"),
    )

    from src.modules.inventory.infrastructure.models import Stock
    with TestSession() as s:
        stock = s.scalar(
            select(Stock).where(Stock.sku_id == uuid.UUID(ids["sku_id"]))
        )
        assert stock is not None
        assert stock.cantidad == Decimal("10")


def test_registrar_compra_directa_es_idempotente(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    body = _compra_directa_body(ids, proveedor_id, idempotency_key="cd-key-3")
    r1 = client.post("/api/v1/purchases/compras-directas", headers=h, json=body)
    r2 = client.post("/api/v1/purchases/compras-directas", headers=h, json=body)
    assert r1.json()["id"] == r2.json()["id"]


def test_rol_sin_permiso_purchases_403(env):
    """cocinero (kds.operar/sales.leer) no tiene ningún permiso purchases.*."""
    client, ids, TestSession = env
    with TestSession() as s:
        cocinero = Usuario(username="cocinero1", pin_hash=hash_pin("222222"), tipo="humano")
        s.add(cocinero)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
        s.add(UsuarioRol(usuario_id=cocinero.id, rol_id=rol.id))
        s.commit()

    h_cocinero = _token(client, "cocinero1", "222222")
    r = _crear_proveedor(client, h_cocinero, ids)
    assert r.status_code == 403


def test_rol_comprador_puede_leer_articulos_para_armar_una_oc():
    """El combo de artículos de la OC llama a `inventory.leer` — sin este
    permiso el front nunca renderiza el formulario de nueva OC."""
    from src.seeders.seed import ROLES

    assert "inventory.leer" in ROLES["comprador"]


# --- La factura del proveedor: datos propios y unicidad por emisor -----------
def _hasta_recibida(client, h, ids, proveedor_id, *, clave="fact"):
    """Deja una OC en `recibida`, que es el estado desde el que se factura."""
    oc = _crear_oc(client, h, ids, proveedor_id, idempotency_key=f"oc-factura-{clave}")
    oc_id = oc.json()["id"]
    client.post(f"/api/v1/purchases/ordenes-compra/{oc_id}/emitir", headers=h)
    item_id = client.get(
        f"/api/v1/purchases/ordenes-compra/{oc_id}", headers=h
    ).json()["items"][0]["id"]
    client.post(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/recepciones", headers=h,
        json={
            "idempotency_key": f"recepcion-{clave}",
            "items": [{"orden_compra_item_id": item_id, "cantidad_recibida": "100"}],
        },
    )
    return oc_id


def _facturar(client, h, oc_id, **overrides):
    cuerpo = {
        "idempotency_key": f"conf-{oc_id[:8]}",
        "tipo": "factura",
        "serie": "F001",
        "correlativo": 1,
        "sustento": "contrato_credito",
    }
    cuerpo.update(overrides)
    return client.post(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/conformidad-comprobante",
        headers=h, json=cuerpo,
    )


def test_la_factura_guarda_fecha_total_y_emisor(env):
    """Los tres datos que la factura del proveedor no podía representar: la
    fecha era `created_at` (cuándo se tecleó), el importe se tomaba de la OC
    —que es la base de lo recibido— y el emisor no viajaba."""
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_id = _hasta_recibida(client, h, ids, proveedor_id)

    r = _facturar(client, h, oc_id, fecha_emision="2026-08-25", total="1180.00")
    assert r.status_code == 201
    assert r.json()["fecha_emision"] == "2026-08-25"
    assert Decimal(r.json()["total"]) == Decimal("1180.00")
    # No se teclea: el emisor es el proveedor de la OC.
    assert r.json()["emisor_num_doc"] == "20111111111"


def test_la_factura_no_puede_emitirse_manana(env):
    """409 y no 422: es una regla de negocio, no un formato mal escrito, y el
    proyecto mapea `ReglaNegocio` a 409 (igual que recibir más de lo
    ordenado). La fecha se compara contra el día del negocio, no el del
    servidor."""
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_id = _hasta_recibida(client, h, ids, proveedor_id)

    manana = (fechas.hoy() + timedelta(days=1)).isoformat()
    r = _facturar(client, h, oc_id, fecha_emision=manana)
    assert r.status_code == 409
    assert "mañana" in r.json()["detail"]


def test_un_tipo_de_comprobante_invalido_es_422_y_no_500(env):
    """`tipo` y `sustento` eran `str` libres contra columnas `Enum` con
    CHECK: el valor malo moría en el flush con un 500 que no decía qué campo
    estaba mal."""
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_id = _hasta_recibida(client, h, ids, proveedor_id)

    assert _facturar(client, h, oc_id, tipo="guia").status_code == 422
    assert _facturar(client, h, oc_id, sustento="trueque").status_code == 422
    # `nc` está en el enum de la columna y **no** en el de la API: una nota de
    # crédito recibida no tiene todavía flujo que la aplique.
    assert _facturar(client, h, oc_id, tipo="nc").status_code == 422


def test_dos_proveedores_pueden_emitir_la_misma_serie_y_correlativo(env):
    """El F001-1 de la molinera y el de la ferretería son documentos
    distintos. La constraint global los hacía chocar."""
    client, ids, _ = env
    h = _token(client)
    uno = _crear_proveedor(client, h, ids).json()["id"]
    otro = _crear_proveedor(
        client, h, ids, razon_social="Ferretería EIRL", ruc="20222222222",
    ).json()["id"]

    oc_uno = _hasta_recibida(client, h, ids, uno, clave="a")
    oc_otro = _hasta_recibida(client, h, ids, otro, clave="b")

    assert _facturar(client, h, oc_uno).status_code == 201
    assert _facturar(client, h, oc_otro).status_code == 201


def test_el_mismo_proveedor_no_repite_serie_y_correlativo(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_uno = _hasta_recibida(client, h, ids, proveedor_id, clave="a")
    oc_dos = _hasta_recibida(client, h, ids, proveedor_id, clave="b")

    assert _facturar(client, h, oc_uno).status_code == 201
    r = _facturar(client, h, oc_dos)
    assert r.status_code == 409
    # El mensaje nombra el documento: un 409 pelado no dice cuál repetiste.
    assert "F001-1" in r.json()["detail"]


def test_una_factura_recibida_no_bloquea_la_serie_propia(env):
    """La constraint global hacía que registrar una compra F001-500 impidiera
    emitir nuestro propio F001-500 — y que el siguiente correlativo propio
    saltara a 501, un salto de numeración ante SUNAT provocado por el papel
    de un tercero."""
    client, ids, TestSession = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_id = _hasta_recibida(client, h, ids, proveedor_id)
    assert _facturar(client, h, oc_id, correlativo=500).status_code == 201

    from src.modules.sales.infrastructure.repositories import ComprobanteRepo
    with TestSession() as s:
        empresa_id = s.scalar(select(Empresa.id))
        assert ComprobanteRepo(s).siguiente_correlativo(empresa_id, "F001") == 1


def test_los_literales_de_la_api_no_se_separan_del_dominio(env):
    """`schemas.TipoRecibido` se escribe a mano porque `Literal[*tupla]` no le
    sirve al type checker ni a OpenAPI. Esto es lo que impide que las dos
    listas se separen."""
    from typing import get_args

    from src.modules.purchases.api import schemas
    from src.modules.purchases.domain import rules

    assert get_args(schemas.TipoRecibido) == rules.TIPOS_COMPROBANTE_RECIBIDO
    assert get_args(schemas.Sustento) == rules.SUSTENTOS_COMPROBANTE


def test_la_ficha_de_la_oc_lee_sus_recepciones_y_su_factura(env):
    """Sin estas dos lecturas la ficha no puede mostrar qué se recibió ni si
    ya se facturó, y ofrecería registrar la factura dos veces."""
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]
    oc_id = _hasta_recibida(client, h, ids, proveedor_id)

    recepciones = client.get(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/recepciones", headers=h
    ).json()
    assert len(recepciones) == 1
    assert Decimal(recepciones[0]["items"][0]["cantidad_recibida"]) == Decimal("100")
    # El artículo sale del ítem de la OC: `recepcion_item` no lo guarda.
    assert recepciones[0]["items"][0]["articulo_id"] == ids["articulo_id"]

    assert client.get(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/comprobantes", headers=h
    ).json() == []
    _facturar(client, h, oc_id)
    comprobantes = client.get(
        f"/api/v1/purchases/ordenes-compra/{oc_id}/comprobantes", headers=h
    ).json()
    assert len(comprobantes) == 1
    assert comprobantes[0]["serie"] == "F001"


def test_el_registro_de_compras_filtra_y_trae_el_proveedor(env):
    client, ids, _ = env
    h = _token(client)
    uno = _crear_proveedor(client, h, ids).json()["id"]
    otro = _crear_proveedor(
        client, h, ids, razon_social="Ferretería EIRL", ruc="20222222222",
    ).json()["id"]
    _facturar(client, h, _hasta_recibida(client, h, ids, uno, clave="a"))
    _facturar(client, h, _hasta_recibida(client, h, ids, otro, clave="b"))

    todos = client.get("/api/v1/purchases/comprobantes", headers=h).json()
    assert todos["total"] == 2
    # El proveedor y el total de la OC se componen después de paginar.
    assert {c["proveedor"] for c in todos["items"]} == {
        "Molinera SAC", "Ferretería EIRL",
    }
    assert all(Decimal(c["total_orden"]) == Decimal("1000.00") for c in todos["items"])

    solo_uno = client.get(
        f"/api/v1/purchases/comprobantes?proveedor_id={uno}", headers=h
    ).json()
    assert solo_uno["total"] == 1
    assert solo_uno["items"][0]["proveedor"] == "Molinera SAC"


def test_el_registro_de_compras_lo_ve_el_contador(env):
    """El contador necesita el documento fuente del asiento sin que haya que
    darle el módulo de compras entero, que además lo dejaría emitir OC."""
    client, ids, TestSession = env
    h_admin = _token(client)
    proveedor_id = _crear_proveedor(client, h_admin, ids).json()["id"]
    _facturar(client, h_admin, _hasta_recibida(client, h_admin, ids, proveedor_id))

    with TestSession() as s:
        rol = s.scalar(select(Rol).where(Rol.nombre == "contador"))
        sucursal_id = s.scalar(select(Sucursal.id))
        contador = Usuario(
            username="contador_pruebas", pin_hash=hash_pin("999999"), tipo="humano",
        )
        s.add(contador)
        s.flush()
        s.add_all([
            UsuarioRol(usuario_id=contador.id, rol_id=rol.id),
            UsuarioSucursal(usuario_id=contador.id, sucursal_id=sucursal_id),
        ])
        s.commit()

    h = _token(client, username="contador_pruebas", pin="999999")
    assert client.get("/api/v1/purchases/comprobantes", headers=h).status_code == 200
    # Y sigue sin poder emitir una OC.
    assert client.post(
        "/api/v1/purchases/ordenes-compra", headers=h,
        json={
            "proveedor_id": proveedor_id, "almacen_destino_id": ids["almacen_id"],
            "idempotency_key": "no-deberia-crear",
            "items": [{"articulo_id": ids["articulo_id"], "cantidad": "1", "costo_unitario": "1"}],
        },
    ).status_code == 403


def test_la_compra_directa_guarda_los_datos_de_la_factura(env):
    client, ids, _ = env
    h = _token(client)
    proveedor_id = _crear_proveedor(client, h, ids).json()["id"]

    cuerpo = _compra_directa_body(ids, proveedor_id)
    cuerpo["comprobante"].update(fecha_emision="2026-08-20", total="59.00")
    r = client.post("/api/v1/purchases/compras-directas", headers=h, json=cuerpo)

    assert r.status_code == 201
    assert r.json()["fecha_emision"] == "2026-08-20"
    assert Decimal(r.json()["total"]) == Decimal("59.00")
    assert r.json()["emisor_num_doc"] == "20111111111"
