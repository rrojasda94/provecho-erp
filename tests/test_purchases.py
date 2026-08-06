"""Tests del slice purchases core: proveedores y ciclo de OC (crear → emitir
→ recibir → anular). SQLite en memoria + override de get_db, mismo patrón
que test_inventory.py.
"""

import uuid
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
