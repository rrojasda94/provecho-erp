"""Merma y devolución (RN-INV-012/017/019/020).

Lo que importa acá no son las tablas: es que el stock inservible **deje de
poder venderse sin dejar de existir** —sigue en el estante hasta que alguien
lo tire— y que una devolución mueva stock real en la dirección correcta
según quién devuelve.
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
from src.core.events import event_bus
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    MovimientoInventario,
    Sku,
    UnidadMedida,
)
from src.modules.purchases.infrastructure.models import Proveedor
from src.modules.users.api.deps import get_db
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

COSTO_QUESO = Decimal("20.0000")


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
        central = Almacen(
            empresa_id=empresa.id, nombre="Central", tipo="central",
            direccion="Jr. Ramón Castilla 248",
        )
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="Tarapoto Centro",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        s.add_all([udm, central, sucursal])
        s.flush()
        queso = Articulo(
            empresa_id=empresa.id, id_interno="Q001", nombre="Queso",
            unidad_medida_id=udm.id, tipo="insumo", controla_lote=True,
            costo_promedio=COSTO_QUESO,
        )
        servilleta = Articulo(
            empresa_id=empresa.id, id_interno="S001", nombre="Servilleta",
            unidad_medida_id=udm.id, tipo="suministro",
        )
        s.add_all([queso, servilleta])
        s.flush()
        sku_q = Sku(articulo_id=queso.id, codigo="SKU-QUESO")
        sku_s = Sku(articulo_id=servilleta.id, codigo="SKU-SERV")
        proveedor = Proveedor(
            empresa_id=empresa.id, tipo="juridico", razon_social="Lácteos SAC",
            ruc="20111111111", clasificacion="preferente", condicion_pago="contado",
        )
        almacenero = Usuario(
            username="almacenero1", pin_hash=hash_pin("654321"), tipo="humano",
        )
        s.add_all([sku_q, sku_s, proveedor, almacenero])
        s.flush()
        rol_alm = s.scalar(select(Rol).where(Rol.nombre == "almacenero"))
        s.add_all([
            UsuarioRol(usuario_id=almacenero.id, rol_id=rol_alm.id),
            UsuarioSucursal(usuario_id=almacenero.id, sucursal_id=sucursal.id),
        ])
        ids.update(
            empresa_id=str(empresa.id), central_id=str(central.id),
            sku_queso=str(sku_q.id), sku_servilleta=str(sku_s.id),
            queso_id=str(queso.id), proveedor_id=str(proveedor.id),
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


def _ingresar(client, h, ids, sku, cantidad):
    r = client.post("/api/v1/inventory/movimientos", headers=h, json={
        "almacen_id": ids["central_id"], "sku_id": sku,
        "cantidad": str(cantidad), "tipo": "recepcion_compra",
    })
    assert r.status_code == 201, r.text
    return r.json()[0]["lote_id"]


def _stock(client, h, ids, sku):
    filas = client.get(
        f"/api/v1/inventory/stock?almacen_id={ids['central_id']}", headers=h
    ).json()["items"]
    return next(f for f in filas if f["sku_id"] == sku)


# --- Merma ------------------------------------------------------------------
def test_la_merma_saca_de_la_venta_sin_sacar_del_almacen(env):
    """RN-INV-012: sigue físicamente ahí —el conteo lo va a encontrar— pero
    no se puede comprometer. Descontarlo al registrarlo haría que el conteo
    cíclico lo declarara sobrante al día siguiente."""
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 100)

    r = client.post("/api/v1/inventory/mermas", headers=h_alm, json={
        "almacen_id": ids["central_id"], "sku_id": ids["sku_servilleta"],
        "cantidad": "30", "motivo": "auditoria",
    })
    assert r.status_code == 201, r.text

    fila = _stock(client, h_alm, ids, ids["sku_servilleta"])
    assert Decimal(fila["cantidad"]) == Decimal("100")  # el físico no se movió
    assert Decimal(fila["disponible"]) == Decimal("70")  # pero no se vende


def test_quien_registra_la_merma_no_firma_su_baja(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 100)
    merma = client.post("/api/v1/inventory/mermas", headers=h_alm, json={
        "almacen_id": ids["central_id"], "sku_id": ids["sku_servilleta"],
        "cantidad": "30", "motivo": "auditoria",
    }).json()

    # El almacenero no tiene `aprobar_ajuste`: 403 por permiso.
    assert client.post(
        f"/api/v1/inventory/mermas/{merma['id']}/resolver", headers=h_alm,
        json={"destino": "desecho"},
    ).status_code == 403


def test_desechar_saca_el_stock_y_avisa_a_contabilidad(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 100)
    merma = client.post("/api/v1/inventory/mermas", headers=h_alm, json={
        "almacen_id": ids["central_id"], "sku_id": ids["sku_servilleta"],
        "cantidad": "30", "motivo": "rechazo_sucursal",
    }).json()

    avisos = []
    event_bus.subscribe("inventory.merma_registrada", avisos.append)
    r = client.post(
        f"/api/v1/inventory/mermas/{merma['id']}/resolver", headers=h_admin,
        json={"destino": "desecho"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "consumida"

    fila = _stock(client, h_admin, ids, ids["sku_servilleta"])
    # Recién ahora baja el físico, y la reserva se cierra con él: el
    # disponible no puede quedar descontado dos veces.
    assert Decimal(fila["cantidad"]) == Decimal("70")
    assert Decimal(fila["disponible"]) == Decimal("70")
    assert len(avisos) == 1
    assert avisos[0]["motivo"] == "rechazo_sucursal"


def test_reintegrar_devuelve_la_merma_a_disponible_sin_asentar_nada(env):
    """La auditoría dijo que servía: no hay pérdida que asentar."""
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 100)
    merma = client.post("/api/v1/inventory/mermas", headers=h_alm, json={
        "almacen_id": ids["central_id"], "sku_id": ids["sku_servilleta"],
        "cantidad": "30", "motivo": "auditoria",
    }).json()

    avisos = []
    event_bus.subscribe("inventory.merma_registrada", avisos.append)
    r = client.post(
        f"/api/v1/inventory/mermas/{merma['id']}/resolver", headers=h_admin,
        json={"destino": "reintegro"},
    )
    assert r.status_code == 200, r.text

    fila = _stock(client, h_admin, ids, ids["sku_servilleta"])
    assert Decimal(fila["disponible"]) == Decimal("100")
    assert avisos == []


def test_el_desecho_saca_el_lote_apartado_y_no_el_que_fefo_elegiria(env):
    """Lo que se tira es un lote concreto. Sin `lote_id` en la reserva, la
    salida tomaría el que vence antes — que puede ser justamente el bueno."""
    client, ids, TestSession = env
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)
    primero = _ingresar(client, h_alm, ids, ids["sku_queso"], 10)
    with TestSession() as s:
        from src.modules.inventory.infrastructure.models import Lote

        s.get(Lote, uuid.UUID(primero)).codigo = "L-BUENO"
        s.commit()
    # Segundo lote, del mismo día: se crea uno nuevo forzando otro código.
    r = client.post("/api/v1/inventory/lotes", headers=h_admin, json={
        "articulo_id": ids["queso_id"], "codigo": "L-DAÑADO", "origen": "compra",
    })
    segundo = r.json()["id"]
    client.post("/api/v1/inventory/movimientos", headers=h_alm, json={
        "almacen_id": ids["central_id"], "sku_id": ids["sku_queso"],
        "cantidad": "10", "tipo": "recepcion_compra", "lote_id": segundo,
    })

    merma = client.post("/api/v1/inventory/mermas", headers=h_alm, json={
        "almacen_id": ids["central_id"], "sku_id": ids["sku_queso"],
        "cantidad": "4", "motivo": "auditoria", "lote_id": segundo,
    }).json()
    assert client.post(
        f"/api/v1/inventory/mermas/{merma['id']}/resolver", headers=h_admin,
        json={"destino": "desecho"},
    ).status_code == 200

    with TestSession() as s:
        salida = s.scalar(
            select(MovimientoInventario).where(MovimientoInventario.cantidad < 0)
        )
    assert str(salida.lote_id) == segundo  # el dañado, no el que vence antes
    assert "desecho de merma" in salida.motivo_lote


# --- Devolución a proveedor ---------------------------------------------------
def test_devolver_al_proveedor_saca_el_lote_declarado_y_avisa_a_compras(env):
    client, ids, TestSession = env
    h_alm = _token(client, "almacenero1", "654321")
    lote = _ingresar(client, h_alm, ids, ids["sku_queso"], 10)

    avisos = []
    event_bus.subscribe("inventory.devolucion_a_proveedor", avisos.append)
    r = client.post("/api/v1/inventory/devoluciones", headers=h_alm, json={
        "almacen_id": ids["central_id"], "origen": "proveedor",
        "referencia_id": ids["proveedor_id"], "motivo": "vencido",
        "items": [{"sku_id": ids["sku_queso"], "cantidad": "4", "lote_id": lote}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["reporte_dirigido_a"] == "almacen"  # RN-INV-020

    assert Decimal(
        _stock(client, h_alm, ids, ids["sku_queso"])["cantidad"]
    ) == Decimal("6")
    assert len(avisos) == 1
    assert avisos[0]["items"][0]["lote_id"] == lote
    # Quién la registró: el reclamo al proveedor tiene dueño (RN-INV-020).
    assert avisos[0]["registrado_por"] is not None


def test_devolver_un_articulo_con_lote_sin_decir_cual_se_rechaza(env):
    """El reclamo al proveedor tiene que decir qué mercadería se rechaza."""
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _ingresar(client, h_alm, ids, ids["sku_queso"], 10)
    r = client.post("/api/v1/inventory/devoluciones", headers=h_alm, json={
        "almacen_id": ids["central_id"], "origen": "proveedor",
        "referencia_id": ids["proveedor_id"], "motivo": "vencido",
        "items": [{"sku_id": ids["sku_queso"], "cantidad": "4"}],
    })
    assert r.status_code == 409
    assert "debe indicar cuál" in r.json()["detail"]


def test_la_devolucion_a_proveedor_emite_su_guia(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    lote = _ingresar(client, h_alm, ids, ids["sku_queso"], 10)
    devolucion = client.post("/api/v1/inventory/devoluciones", headers=h_alm, json={
        "almacen_id": ids["central_id"], "origen": "proveedor",
        "referencia_id": ids["proveedor_id"], "motivo": "dañado",
        "items": [{"sku_id": ids["sku_queso"], "cantidad": "4", "lote_id": lote}],
    }).json()

    r = client.post(
        f"/api/v1/inventory/devoluciones/{devolucion['id']}/guia-remision",
        headers=h_alm,
        json={
            "lugar_destino": "Av. Industrial 500 - Lima",
            "chofer_nombres": "Luis", "chofer_apellidos": "Pérez",
            "chofer_num_doc": "44556677", "chofer_licencia": "Q44556677",
            "vehiculo_placa": "ABC-123", "peso_bruto_kg": "12.5",
        },
    )
    assert r.status_code == 201, r.text
    guia = r.json()
    assert guia["devolucion_id"] == devolucion["id"]
    assert guia["transferencia_id"] is None
    # `13` (otros): SUNAT no tiene código para "devolución al proveedor", y
    # `04` sería declarar un traslado entre locales propios que no es.
    assert guia["motivo_traslado"] == "13"
    assert guia["ruc_receptor"] == "20111111111"

    # Idempotente: pedirla dos veces no numera una segunda.
    otra = client.post(
        f"/api/v1/inventory/devoluciones/{devolucion['id']}/guia-remision",
        headers=h_alm,
        json={
            "lugar_destino": "Av. Industrial 500 - Lima",
            "chofer_nombres": "Luis", "chofer_apellidos": "Pérez",
            "chofer_num_doc": "44556677", "chofer_licencia": "Q44556677",
            "vehiculo_placa": "ABC-123", "peso_bruto_kg": "12.5",
        },
    )
    assert otra.json()["id"] == guia["id"]

    # Con guía emitida, anular exige la comunicación de baja ante SUNAT.
    assert client.post(
        f"/api/v1/inventory/devoluciones/{devolucion['id']}/anular", headers=h_alm
    ).status_code == 409


# --- Devolución de cliente ----------------------------------------------------
def test_lo_que_devuelve_un_cliente_para_reintegro_vuelve_al_estante(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 10)

    r = client.post("/api/v1/inventory/devoluciones", headers=h_alm, json={
        "almacen_id": ids["central_id"], "origen": "cliente",
        "motivo": "no_requerido", "destino": "reintegro",
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "3"}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["reporte_dirigido_a"] == "comercial"  # RN-INV-020

    fila = _stock(client, h_alm, ids, ids["sku_servilleta"])
    assert Decimal(fila["cantidad"]) == Decimal("13")
    assert Decimal(fila["disponible"]) == Decimal("13")


def test_lo_que_devuelve_un_cliente_para_desecho_entra_apartado(env):
    """Entró al almacén pero no al estante: se aparta como merma en el mismo
    acto, o la próxima venta se lo lleva."""
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 10)

    r = client.post("/api/v1/inventory/devoluciones", headers=h_alm, json={
        "almacen_id": ids["central_id"], "origen": "cliente",
        "motivo": "dañado", "destino": "desecho",
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "3"}],
    })
    assert r.status_code == 201, r.text

    fila = _stock(client, h_alm, ids, ids["sku_servilleta"])
    assert Decimal(fila["cantidad"]) == Decimal("13")  # está físicamente
    assert Decimal(fila["disponible"]) == Decimal("10")  # pero no se vende
    mermas = client.get("/api/v1/inventory/mermas", headers=h_alm).json()
    assert len(mermas) == 1
    assert mermas[0]["motivo"] == "devolucion"


def test_una_devolucion_de_cliente_exige_destino(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 10)
    r = client.post("/api/v1/inventory/devoluciones", headers=h_alm, json={
        "almacen_id": ids["central_id"], "origen": "cliente",
        "motivo": "dañado",
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "3"}],
    })
    assert r.status_code == 409
    assert "exige destino" in r.json()["detail"]


def test_anular_repone_lo_que_la_devolucion_movio(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _ingresar(client, h_alm, ids, ids["sku_servilleta"], 10)
    devolucion = client.post("/api/v1/inventory/devoluciones", headers=h_alm, json={
        "almacen_id": ids["central_id"], "origen": "cliente",
        "motivo": "dañado", "destino": "desecho",
        "items": [{"sku_id": ids["sku_servilleta"], "cantidad": "3"}],
    }).json()

    r = client.post(
        f"/api/v1/inventory/devoluciones/{devolucion['id']}/anular", headers=h_alm
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "anulada"

    fila = _stock(client, h_alm, ids, ids["sku_servilleta"])
    assert Decimal(fila["cantidad"]) == Decimal("10")
    # La merma que había apartado también se soltó: si no, el disponible
    # quedaría descontado por una reserva que ya no respalda nada.
    assert Decimal(fila["disponible"]) == Decimal("10")
    assert client.get("/api/v1/inventory/mermas", headers=h_alm).json() == []
