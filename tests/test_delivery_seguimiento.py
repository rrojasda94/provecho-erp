"""Enlace público de seguimiento del cliente (RN-DLV-008, ADR-098):
respuesta mínima, 404 uniforme para token inexistente/vencido, posición
solo mientras la parada está en camino, sin caché y con límite por IP.
"""

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
from src.modules.delivery.infrastructure.models import Entrega
from src.modules.rrhh.infrastructure.models import Trabajador
from src.modules.sales.application import listeners as sales_listeners
from src.modules.sales.infrastructure.models import ProductoComercial, PuntoVenta, Venta, VentaItem
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

LAT_LOCAL = Decimal("-6.487000")
LNG_LOCAL = Decimal("-76.363000")
LAT_CLIENTE = Decimal("-6.490000")
LNG_CLIENTE = Decimal("-76.360000")

PUBLICO = "/api/v1/delivery/publico"


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

        persona = Persona(nombres="Kevin", apellidos="Ríos")
        s.add(persona)
        s.flush()
        usuario_rep = Usuario(
            username="kevinrep", pin_hash=hash_pin("111111"), tipo="humano", persona_id=persona.id
        )
        s.add(usuario_rep)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.nombre == "repartidor"))
        s.add(UsuarioRol(usuario_id=usuario_rep.id, rol_id=rol.id))
        s.add(UsuarioSucursal(usuario_id=usuario_rep.id, sucursal_id=sucursal.id))
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
        repartidor = repartidores_uc.crear(
            s,
            empresa_id=empresa.id,
            trabajador_id=trabajador.id,
            sucursal_id=sucursal.id,
            vehiculo_tipo="moto",
        )
        s.flush()

        headers["aprobador1"] = auth_headers(s, "aprobador1")
        headers["kevinrep"] = auth_headers(s, "kevinrep")
        ids.update(
            empresa_id=str(empresa.id),
            sucursal_id=str(sucursal.id),
            producto_id=str(producto.id),
            repartidor_id=str(repartidor.id),
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


def _crear_venta_delivery(session, ids) -> Venta:
    venta = Venta(
        sucursal_id=uuid.UUID(ids["sucursal_id"]),
        numero_orden=int(uuid.uuid4().int % 100000),
        punto_venta_id=session.scalar(select(PuntoVenta.id)),
        canal="pdv",
        modalidad="delivery",
        usuario_id=session.scalar(select(Usuario.id).where(Usuario.username == "cajero1")),
        estado="pagada",
        total=Decimal("35.00"),
        idempotency_key=str(uuid.uuid4()),
        direccion_entrega="Jr. Amazonas 123",
        ubicacion_lat=LAT_CLIENTE,
        ubicacion_lng=LNG_CLIENTE,
    )
    session.add(venta)
    session.flush()
    session.add(
        VentaItem(
            venta_id=venta.id,
            producto_comercial_id=uuid.UUID(ids["producto_id"]),
            cantidad=Decimal(1),
            precio_unitario=Decimal("35.00"),
            estado_preparacion="listo",
        )
    )
    session.flush()
    session.commit()
    return venta


def _asignar_ruta(client, ids, headers, TestSession) -> tuple[str, str]:
    """Crea una venta y una ruta con esa única parada. Devuelve
    (ruta_id, token_publico)."""
    with TestSession() as s:
        venta = _crear_venta_delivery(s, ids)
        venta_id = str(venta.id)
    r = client.post(
        "/api/v1/delivery/rutas",
        headers=headers["aprobador1"],
        json={
            "sucursal_id": ids["sucursal_id"],
            "repartidor_id": ids["repartidor_id"],
            "venta_ids": [venta_id],
        },
    )
    assert r.status_code == 201, r.text
    ruta_id = r.json()["id"]
    with TestSession() as s:
        entrega = s.scalar(select(Entrega).where(Entrega.ruta_id == uuid.UUID(ruta_id)))
        token = entrega.token_publico
    return ruta_id, token


def test_token_inexistente_da_404(env):
    client, *_ = env
    r = client.get(f"{PUBLICO}/seguimiento/token-que-no-existe")
    assert r.status_code == 404


def test_asignada_todavia_esta_preparando_sin_posicion(env):
    client, ids, headers, TestSession = env
    _ruta_id, token = _asignar_ruta(client, ids, headers, TestSession)

    r = client.get(f"{PUBLICO}/seguimiento/{token}")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado_publico"] == "preparando"
    assert cuerpo["posicion"] is None
    assert cuerpo["destino"]["lat"] is not None


def test_en_camino_expone_la_ultima_posicion_conocida(env):
    client, ids, headers, TestSession = env
    ruta_id, token = _asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    ahora = datetime.now(UTC)
    r_pin = client.post(
        f"/api/v1/delivery/rutas/{ruta_id}/posiciones",
        headers=headers["kevinrep"],
        json={"lat": "-6.4885", "lng": "-76.3615", "registrado_at": ahora.isoformat()},
    )
    assert r_pin.status_code == 204

    r = client.get(f"{PUBLICO}/seguimiento/{token}")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado_publico"] == "en_camino"
    assert cuerpo["posicion"] is not None
    assert Decimal(cuerpo["posicion"]["lat"]) == Decimal("-6.488500")
    assert cuerpo["repartidor"] == {"nombre": "Kevin"}


def test_entregado_ya_no_expone_posicion(env):
    client, ids, headers, TestSession = env
    ruta_id, token = _asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    with TestSession() as s:
        entrega = s.scalar(select(Entrega).where(Entrega.token_publico == token))
        entrega_id = str(entrega.id)
    client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["kevinrep"],
        json={},
    )

    r = client.get(f"{PUBLICO}/seguimiento/{token}")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado_publico"] == "entregado"
    assert cuerpo["posicion"] is None
    assert any(h["hito"] == "entregado" for h in cuerpo["linea_tiempo"])


def test_token_vencido_da_404_igual_que_inexistente(env):
    client, ids, headers, TestSession = env
    _ruta_id, token = _asignar_ruta(client, ids, headers, TestSession)
    with TestSession() as s:
        entrega = s.scalar(select(Entrega).where(Entrega.token_publico == token))
        entrega.token_expira_at = datetime.now(UTC) - timedelta(hours=1)
        s.commit()

    r = client.get(f"{PUBLICO}/seguimiento/{token}")
    assert r.status_code == 404


def test_respuesta_no_se_cachea(env):
    client, ids, headers, TestSession = env
    _ruta_id, token = _asignar_ruta(client, ids, headers, TestSession)
    r = client.get(f"{PUBLICO}/seguimiento/{token}")
    assert r.headers["cache-control"] == "no-store"


def test_el_rate_limit_del_seguimiento_corta(env, monkeypatch):
    from src.core import rate_limit

    client, ids, headers, TestSession = env
    _ruta_id, token = _asignar_ruta(client, ids, headers, TestSession)

    llamadas = {"n": 0}

    def _contar(nombre, sujeto, intentos, ventana):
        if nombre != "seguimiento_publico":
            return
        llamadas["n"] += 1
        if llamadas["n"] > intentos:
            from fastapi import HTTPException, status

            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas solicitudes")

    monkeypatch.setattr(rate_limit, "consumir", _contar)
    codigos = [client.get(f"{PUBLICO}/seguimiento/{token}").status_code for _ in range(125)]
    assert 429 in codigos
