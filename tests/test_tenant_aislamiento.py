"""Tests de aislamiento de tenant (ADR-004): el alcance sale del JWT, no del
request. Un usuario de la empresa/sucursal A nunca toca datos de la B.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.core.tenant import FueraDeAlcance, Tenant
from src.modules.inventory.application import listeners
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    UnidadMedida,
)
from src.modules.sales.infrastructure.models import (
    ListaPrecio,
    Precio,
    ProductoComercial,
    PuntoVenta,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Persona,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin


def _sucursal(s, marca, empresa, nombre):
    suc = Sucursal(
        marca_id=marca.id, empresa_id=empresa.id, nombre=nombre,
        direccion="Jr. X 123", tenencia="alquilada",
    )
    s.add(suc)
    s.flush()
    return suc


def _usuario(s, username, sucursal, rol):
    u = Usuario(username=username, pin_hash=hash_pin("654321"), tipo="humano")
    s.add(u)
    s.flush()
    s.add_all([
        UsuarioRol(usuario_id=u.id, rol_id=rol.id),
        UsuarioSucursal(usuario_id=u.id, sucursal_id=sucursal.id),
    ])
    return u


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
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca))
        empresa_a = s.scalar(select(Empresa))
        empresa_b = Empresa(
            grupo_id=grupo.id, ruc="20600000001", razon_social="Otra EIRL",
            domicilio_fiscal="Lima", tipo="operativa",
            zona_tributaria="amazonia_ley27037",
        )
        s.add(empresa_b)
        s.flush()

        suc_a = _sucursal(s, marca, empresa_a, "Sucursal A")
        suc_b = _sucursal(s, marca, empresa_b, "Sucursal B")
        alm_a = Almacen(empresa_id=empresa_a.id, sucursal_id=suc_a.id,
                        nombre="Alm A", tipo="sucursal")
        alm_b = Almacen(empresa_id=empresa_b.id, sucursal_id=suc_b.id,
                        nombre="Alm B", tipo="sucursal")
        pv_a = PuntoVenta(sucursal_id=suc_a.id, canal="trabajador",
                          serie_boleta="B001", serie_factura="F001",
                          politica_pago="adelantado")
        pv_b = PuntoVenta(sucursal_id=suc_b.id, canal="trabajador",
                          serie_boleta="B002", serie_factura="F002",
                          politica_pago="adelantado")
        udm_cat = CategoriaUdm(nombre="Peso")
        s.add_all([alm_a, alm_b, pv_a, pv_b, udm_cat])
        s.flush()
        udm = UnidadMedida(categoria_udm_id=udm_cat.id, nombre="Kilo")
        s.add(udm)
        s.flush()
        art_b = Articulo(empresa_id=empresa_b.id, id_interno="B001",
                         nombre="Insumo B", unidad_medida_id=udm.id, tipo="insumo")
        receta = Receta(nombre="Pizza", rendimiento_cantidad=Decimal(1),
                        rendimiento_unidad_medida_id=udm.id)
        s.add_all([art_b, receta])
        s.flush()
        producto = ProductoComercial(id_interno="P001", marca_id=marca.id,
                                     nombre="Pizza", receta_id=receta.id)
        s.add(producto)
        s.flush()
        lista = ListaPrecio(marca_id=marca.id, nombre="Regular",
                            vigente_desde=date(2020, 1, 1))
        s.add(lista)
        s.flush()
        s.add(Precio(lista_precio_id=lista.id, producto_comercial_id=producto.id,
                     monto=Decimal("25.00")))

        def _rol(nombre):
            return s.scalar(select(Rol).where(Rol.nombre == nombre))

        cajero_a = _usuario(s, "cajero_a", suc_a, _rol("cajero"))
        _usuario(s, "almacenero_a", suc_a, _rol("almacenero"))
        _usuario(s, "comprador_a", suc_a, _rol("comprador"))
        _usuario(s, "jefe_cocina_a", suc_a, _rol("jefe_cocina"))
        _usuario(s, "contador_a", suc_a, _rol("contador"))
        _usuario(s, "rrhh_a", suc_a, _rol("rrhh_admin"))

        persona = Persona(
            nombres="Ana", apellidos="Torres", tipo_documento="dni",
            numero_documento="10000123",
        )
        s.add(persona)
        s.flush()

        ids.update(
            suc_a=str(suc_a.id), suc_b=str(suc_b.id),
            pv_a=str(pv_a.id), pv_b=str(pv_b.id),
            alm_a=str(alm_a.id), alm_b=str(alm_b.id),
            producto=str(producto.id), marca=str(marca.id),
            empresa_a=str(empresa_a.id), empresa_b=str(empresa_b.id),
            art_b=str(art_b.id), persona=str(persona.id),
            cajero_a=str(cajero_a.id),
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
        yield c, ids


def _token(client, username, pin="654321"):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _venta_body(ids, sucursal, pv, key):
    return {
        "sucursal_id": sucursal, "punto_venta_id": pv, "canal": "pdv",
        "modalidad": "takeout", "idempotency_key": key,
        "items": [{"producto_comercial_id": ids["producto"], "cantidad": "1"}],
    }


def test_venta_en_sucursal_ajena_403(env):
    client, ids = env
    h = _token(client, "cajero_a")
    ok = client.post("/api/v1/sales/ventas", headers=h,
                     json=_venta_body(ids, ids["suc_a"], ids["pv_a"], "iso-0001"))
    assert ok.status_code == 201
    ajena = client.post("/api/v1/sales/ventas", headers=h,
                        json=_venta_body(ids, ids["suc_b"], ids["pv_b"], "iso-0002"))
    assert ajena.status_code == 403


def test_venta_de_otra_sucursal_no_se_lee(env):
    client, ids = env
    h_admin = _token(client, "admin", "123456")
    venta_b = client.post("/api/v1/sales/ventas", headers=h_admin,
                          json=_venta_body(ids, ids["suc_b"], ids["pv_b"], "iso-0003"))
    assert venta_b.status_code == 201
    h = _token(client, "cajero_a")
    r = client.get(f"/api/v1/sales/ventas/{venta_b.json()['id']}", headers=h)
    assert r.status_code == 403


def test_movimiento_en_almacen_de_otra_empresa_403(env):
    client, ids = env
    h = _token(client, "almacenero_a")
    body = {"sku_id": ids["producto"], "cantidad": "1", "tipo": "recepcion_compra"}
    assert client.post("/api/v1/inventory/movimientos", headers=h,
                       json={**body, "almacen_id": ids["alm_b"]}).status_code == 403


def test_articulo_de_otra_empresa_no_se_edita(env):
    client, ids = env
    h = _token(client, "almacenero_a")
    r = client.patch(f"/api/v1/inventory/articulos/{ids['art_b']}", headers=h,
                     json={"nombre": "Secuestrado"})
    # almacenero no tiene gestionar_catalogo → 403 por permiso, no por tenant.
    assert r.status_code == 403


def test_listado_de_articulos_solo_ve_su_empresa(env):
    client, ids = env
    h = _token(client, "almacenero_a")
    nombres = [a["nombre"] for a in
               client.get("/api/v1/inventory/articulos", headers=h).json()]
    assert "Insumo B" not in nombres


def test_empresa_explicita_ajena_403(env):
    client, ids = env
    h = _token(client, "cajero_a")
    r = client.get(
        f"/api/v1/sales/medios-pago?empresa_id={ids['empresa_b']}", headers=h
    )
    assert r.status_code == 403


# --- purchases / production / accounting / rrhh / dashboard -------------------
def _proveedor_body(**overrides):
    body = {
        "tipo": "juridico", "condicion_pago": "contado",
        "razon_social": "Molinera SAC", "ruc": "20111111111",
    }
    body.update(overrides)
    return body


def test_proveedor_se_crea_en_la_empresa_del_jwt(env):
    client, ids = env
    h = _token(client, "comprador_a")
    r = client.post("/api/v1/purchases/proveedores", headers=h, json=_proveedor_body())
    assert r.status_code == 201
    assert r.json()["empresa_id"] == ids["empresa_a"]


def test_proveedor_con_empresa_ajena_403(env):
    client, ids = env
    h = _token(client, "comprador_a")
    r = client.post("/api/v1/purchases/proveedores", headers=h,
                    json=_proveedor_body(empresa_id=ids["empresa_b"]))
    assert r.status_code == 403


def test_orden_produccion_en_almacen_ajeno_403(env):
    client, ids = env
    h = _token(client, "jefe_cocina_a")
    r = client.post("/api/v1/production/ordenes", headers=h, json={
        "articulo_id": ids["art_b"], "almacen_id": ids["alm_b"],
        "cantidad_planeada": "10", "idempotency_key": "iso-prod-0001",
    })
    assert r.status_code == 403


def test_cuentas_contables_de_empresa_ajena_403(env):
    client, ids = env
    h = _token(client, "contador_a")
    r = client.get(
        f"/api/v1/accounting/cuentas-contables?empresa_id={ids['empresa_b']}", headers=h
    )
    assert r.status_code == 403


def test_abrir_caja_en_punto_venta_ajeno_403(env):
    client, ids = env
    h = _token(client, "cajero_a")
    # El relevo lo firma contabilidad con su PIN, no el cajero desde su
    # sesión (RN-MDP-002).
    autorizacion = client.post(
        "/api/v1/auth/autorizar",
        json={
            "username": "contador_a",
            "pin": "654321",
            "permiso": "accounting.caja_relevar",
        },
    ).json()["autorizacion"]
    body = {
        "punto_venta_id": ids["pv_b"],
        "monto_declarado": "100.00",
        "detalle_denominaciones": {"50": 2},
        "autorizacion": autorizacion,
    }
    assert client.post("/api/v1/accounting/cajas/apertura",
                       headers=h, json=body).status_code == 403
    body["punto_venta_id"] = ids["pv_a"]
    assert client.post("/api/v1/accounting/cajas/apertura",
                       headers=h, json=body).status_code == 201


def test_trabajador_se_crea_en_la_empresa_del_jwt(env):
    client, ids = env
    h = _token(client, "rrhh_a")
    r = client.post("/api/v1/rrhh/trabajadores", headers=h, json={
        "persona_id": ids["persona"], "cargo": "Mozo", "area": "Salón",
        "tipo_vinculo": "planilla", "fecha_ingreso": "2026-01-01",
    })
    assert r.status_code == 201
    assert r.json()["empresa_id"] == ids["empresa_a"]
    ajeno = client.get(
        f"/api/v1/rrhh/trabajadores?empresa_id={ids['empresa_b']}", headers=h
    )
    assert ajeno.status_code == 403


def test_dashboard_de_empresa_ajena_403(env):
    client, ids = env
    h = _token(client, "contador_a")
    assert client.get("/api/v1/dashboard/resumen", headers=h).status_code == 200
    r = client.get(
        f"/api/v1/dashboard/resumen?empresa_id={ids['empresa_b']}", headers=h
    )
    assert r.status_code == 403


def test_seed_deja_al_admin_con_empresa(env):
    """Regresión: sin `usuario_sucursal` el admin del seeder no tenía
    `empresa_id` en el JWT y toda operación escopada respondía 403."""
    client, ids = env
    h = _token(client, "admin", "123456")
    r = client.post("/api/v1/purchases/proveedores", headers=h,
                    json=_proveedor_body(ruc="20222222222"))
    assert r.status_code == 201
    assert r.json()["empresa_id"] == ids["empresa_a"]


# --- Reglas puras del contexto -----------------------------------------------
def test_tenant_sin_empresa_ni_superusuario_deniega():
    import uuid

    t = Tenant(usuario_id=uuid.uuid4(), empresa_id=None, sucursal_ids=frozenset())
    with pytest.raises(FueraDeAlcance):
        t.empresa()
    with pytest.raises(FueraDeAlcance):
        t.exigir_sucursal(uuid.uuid4())


def test_superusuario_sin_empresa_usa_la_explicita():
    import uuid

    empresa = uuid.uuid4()
    t = Tenant(usuario_id=uuid.uuid4(), empresa_id=None, sucursal_ids=frozenset(),
               superusuario=True)
    assert t.empresa(empresa) == empresa
    assert t.filtro_empresa() is None  # listados: ve todo
