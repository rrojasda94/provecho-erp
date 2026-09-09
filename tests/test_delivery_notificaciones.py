"""Aviso al cliente por WhatsApp y notificación in-app en `delivery`
(ADR-098, slice 6).

No se prueba que WhatsApp funcione — eso ya lo cubre
`tests/test_marketing_encuestas.py` sobre el mismo adaptador — sino que
`delivery` dispare el hito correcto en el momento correcto, que un rechazo
de Meta quede escrito sin reintentar, que sin teléfono no reviente, y que
las notificaciones de bandeja (`users.notificar_a`) lleguen a quien
despachó la ruta.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import Base
from src.modules.delivery.application import entregas as entregas_uc
from src.modules.delivery.application import listeners as delivery_listeners
from src.modules.delivery.application import notificaciones
from src.modules.delivery.application import repartidores as repartidores_uc
from src.modules.delivery.application import tasks as delivery_tasks
from src.modules.delivery.infrastructure.models import Entrega, RutaReparto
from src.modules.rrhh.infrastructure.models import Trabajador
from src.modules.sales.application import listeners as sales_listeners
from src.modules.sales.infrastructure.models import (
    Cliente,
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Notificacion,
    Persona,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared.integrations import whatsapp
from tests.conftest import auth_headers

LAT_LOCAL = Decimal("-6.487000")
LNG_LOCAL = Decimal("-76.363000")
LAT_CLIENTE = Decimal("-6.490000")
LNG_CLIENTE = Decimal("-76.360000")


class ClienteWhatsAppFalso:
    """Doble del adaptador: registra qué se mandó, no habla con nadie."""

    enviados: list[tuple] = []
    rechazar: bool = False

    def enviar_plantilla(self, telefono, nombre, idioma, parametros):
        if self.rechazar:
            raise whatsapp.WhatsAppRechazo("número inválido")
        self.enviados.append(("plantilla", telefono, nombre, tuple(parametros)))
        return "wamid.PLANTILLA"

    def enviar_texto(self, telefono, texto):
        self.enviados.append(("texto", telefono, texto, ()))
        return "wamid.TEXTO"

    def enviar_opciones(self, telefono, texto, opciones):
        self.enviados.append(("opciones", telefono, texto, tuple(opciones)))
        return "wamid.OPCIONES"


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(sales_listeners, "session_factory", TestSession)
    monkeypatch.setattr(delivery_listeners, "session_factory", TestSession)
    monkeypatch.setattr(delivery_tasks, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    headers = {}
    with TestSession() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        marca = s.scalar(select(Marca))
        grupo = s.scalar(select(Grupo))
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

        persona_rep = Persona(nombres="Kevin", apellidos="Ríos")
        s.add(persona_rep)
        s.flush()
        usuario_rep = Usuario(
            username="kevinrep",
            pin_hash=hash_pin("111111"),
            tipo="humano",
            persona_id=persona_rep.id,
        )
        s.add(usuario_rep)
        s.flush()
        rol_rep = s.scalar(select(Rol).where(Rol.nombre == "repartidor"))
        s.add(UsuarioRol(usuario_id=usuario_rep.id, rol_id=rol_rep.id))
        s.add(UsuarioSucursal(usuario_id=usuario_rep.id, sucursal_id=sucursal.id))
        trabajador = Trabajador(
            empresa_id=empresa.id,
            persona_id=persona_rep.id,
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

        persona_cliente = Persona(nombres="Rosa", apellidos="Vela", telefono="987654321")
        s.add(persona_cliente)
        s.flush()
        cliente = Cliente(grupo_id=grupo.id, tipo="natural", persona_id=persona_cliente.id)
        s.add(cliente)
        s.flush()

        aprobador_usuario_id = s.scalar(
            select(Usuario.id).where(Usuario.username == "aprobador1")
        )

        headers["aprobador1"] = auth_headers(s, "aprobador1")
        headers["kevinrep"] = auth_headers(s, "kevinrep")
        ids.update(
            empresa_id=str(empresa.id),
            sucursal_id=str(sucursal.id),
            producto_id=str(producto.id),
            repartidor_id=str(repartidor.id),
            repartidor_usuario_id=str(usuario_rep.id),
            cliente_id=str(cliente.id),
            aprobador_usuario_id=str(aprobador_usuario_id),
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


@pytest.fixture()
def wa(env, monkeypatch):
    """Entorno con WhatsApp 'configurado' y la cola corriendo en línea."""
    client, ids, headers, TestSession = env
    ClienteWhatsAppFalso.enviados = []
    ClienteWhatsAppFalso.rechazar = False
    monkeypatch.setattr(settings, "whatsapp_token", "token-de-prueba")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "1234567890")
    monkeypatch.setattr(settings, "delivery_url_publica", "https://reparto.majambo.pe")
    monkeypatch.setattr(notificaciones, "cliente_factory", ClienteWhatsAppFalso)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    return client, ids, headers, TestSession


def _crear_venta_delivery(session, ids, *, cliente_id=None) -> Venta:
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
        cliente_id=cliente_id,
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


def _crear_y_asignar_ruta(
    client, ids, headers, TestSession, *, con_cliente=True
) -> tuple[str, str]:
    with TestSession() as s:
        cliente_id = uuid.UUID(ids["cliente_id"]) if con_cliente else None
        venta = _crear_venta_delivery(s, ids, cliente_id=cliente_id)
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
        entrega_id = str(entrega.id)
    return ruta_id, entrega_id


# --- Bandeja in-app: ruta asignada ------------------------------------------------
def test_crear_ruta_notifica_in_app_al_repartidor(env):
    client, ids, headers, TestSession = env
    _crear_y_asignar_ruta(client, ids, headers, TestSession)

    with TestSession() as s:
        aviso = s.scalar(
            select(Notificacion).where(
                Notificacion.usuario_id == uuid.UUID(ids["repartidor_usuario_id"]),
                Notificacion.tipo == "delivery.ruta_asignada",
            )
        )
        assert aviso is not None


# --- Aviso "en camino" (delivery.ruta_iniciada) -----------------------------------
def test_iniciar_ruta_avisa_en_camino_por_whatsapp(wa):
    client, ids, headers, TestSession = wa
    ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    assert r.status_code == 200, r.text

    assert len(ClienteWhatsAppFalso.enviados) == 1
    accion, telefono, nombre_plantilla, parametros = ClienteWhatsAppFalso.enviados[0]
    assert accion == "plantilla"
    assert telefono == "987654321"
    assert nombre_plantilla == settings.whatsapp_plantilla_en_camino
    assert parametros[0] == "Rosa Vela"
    assert parametros[1] == "Kevin"

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.aviso_en_camino_at is not None
        assert entrega.aviso_error is None


def test_sin_telefono_deja_aviso_error_sin_reventar(wa):
    client, ids, headers, TestSession = wa
    ruta_id, entrega_id = _crear_y_asignar_ruta(
        client, ids, headers, TestSession, con_cliente=False
    )

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    assert r.status_code == 200, r.text

    assert ClienteWhatsAppFalso.enviados == []
    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.aviso_error == notificaciones.SIN_TELEFONO
        assert entrega.aviso_en_camino_at is None


def test_whatsapp_rechazo_no_reintenta_y_queda_escrito(wa):
    client, ids, headers, TestSession = wa
    ClienteWhatsAppFalso.rechazar = True
    ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    assert r.status_code == 200, r.text

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.aviso_en_camino_at is None
        assert "número inválido" in entrega.aviso_error


def test_sin_whatsapp_configurado_no_encola_nada(env):
    """Sin `env` (sin la fixture `wa`) WhatsApp no está habilitado — el
    tablero se apoya en el enlace copiable, nunca en la cola."""
    client, ids, headers, TestSession = env
    ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    assert r.status_code == 200, r.text

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.aviso_en_camino_at is None
        assert entrega.aviso_error is None


def test_es_hub_no_encola_nada(wa, monkeypatch):
    client, ids, headers, TestSession = wa
    monkeypatch.setattr(settings, "deployment_mode", "hub")
    ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)

    r = client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    assert r.status_code == 200, r.text

    assert ClienteWhatsAppFalso.enviados == []
    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.aviso_en_camino_at is None


# --- Aviso "entregado" y "fallida" -------------------------------------------------
def test_entregar_avisa_entregado_por_whatsapp(wa):
    client, ids, headers, TestSession = wa
    ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    ClienteWhatsAppFalso.enviados = []

    r = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/entregar",
        headers=headers["aprobador1"],
        json={},
    )
    assert r.status_code == 200, r.text

    assert len(ClienteWhatsAppFalso.enviados) == 1
    accion, telefono, nombre_plantilla, parametros = ClienteWhatsAppFalso.enviados[0]
    assert nombre_plantilla == settings.whatsapp_plantilla_entregado
    assert parametros[0] == "Rosa Vela"

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.aviso_resultado_at is not None


def test_fallar_avisa_fallida_por_whatsapp_y_notifica_a_quien_creo_la_ruta(wa):
    client, ids, headers, TestSession = wa
    ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])
    ClienteWhatsAppFalso.enviados = []

    r = client.post(
        f"/api/v1/delivery/entregas/{entrega_id}/fallar",
        headers=headers["aprobador1"],
        json={"motivo": "cliente_ausente"},
    )
    assert r.status_code == 200, r.text

    assert len(ClienteWhatsAppFalso.enviados) == 1
    accion, telefono, nombre_plantilla, parametros = ClienteWhatsAppFalso.enviados[0]
    assert nombre_plantilla == settings.whatsapp_plantilla_entrega_fallida
    assert parametros[0] == "Rosa Vela"
    assert "encontramos" in parametros[1]

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.aviso_resultado_at is not None
        aviso = s.scalar(
            select(Notificacion).where(
                Notificacion.usuario_id == uuid.UUID(ids["aprobador_usuario_id"]),
                Notificacion.tipo == "delivery.entrega_fallida",
            )
        )
        assert aviso is not None


# --- Venta anulada con la entrega ya en_ruta: avisa, no cancela --------------------
def test_venta_anulada_en_ruta_notifica_sin_cancelar(env):
    client, ids, headers, TestSession = env
    ruta_id, entrega_id = _crear_y_asignar_ruta(client, ids, headers, TestSession)
    client.post(f"/api/v1/delivery/rutas/{ruta_id}/iniciar", headers=headers["aprobador1"])

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.estado == "en_ruta"
        venta_id = entrega.venta_id
        entregas_uc.cancelar_por_venta_anulada(s, venta_id)
        s.commit()

    with TestSession() as s:
        entrega = s.get(Entrega, uuid.UUID(entrega_id))
        assert entrega.estado == "en_ruta"
        aviso = s.scalar(
            select(Notificacion).where(
                Notificacion.usuario_id == uuid.UUID(ids["aprobador_usuario_id"]),
                Notificacion.tipo == "delivery.venta_anulada_en_ruta",
            )
        )
        assert aviso is not None
        ruta = s.get(RutaReparto, uuid.UUID(ruta_id))
        assert ruta.creada_por == uuid.UUID(ids["aprobador_usuario_id"])
