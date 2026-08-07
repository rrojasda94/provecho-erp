"""Notificaciones: a quién le llega el aviso y qué pasa cuando no hay nadie.

Lo que importa acá no es la tabla: es que el aviso **llegue a la persona que
está a cargo del local en ese momento**, y que no poder avisar nunca tumbe la
operación que originó el aviso.
"""

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.core.events import event_bus
from src.modules.accounting.application import caja
from src.modules.accounting.application.queries_publicas import encargado_de_turno
from src.modules.sales.infrastructure.models import PuntoVenta
from src.modules.users.application import notificaciones
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Notificacion,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin


@pytest.fixture()
def env():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        grupo = Grupo(nombre="Grupo Majambo")
        s.add(grupo)
        s.flush()
        empresa = Empresa(
            grupo_id=grupo.id, razon_social="Majambo EIRL", ruc="20100000001",
            domicilio_fiscal="Jr. X 1", tipo="operativa",
        )
        marca = Marca(grupo_id=grupo.id, nombre="Charlie's", tipo="restaurante")
        s.add_all([empresa, marca])
        s.flush()
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="CH1",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        s.add(sucursal)
        s.flush()
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador", serie_boleta="B001",
            serie_factura="F001", politica_pago="adelantado",
        )
        rol_sup = Rol(nombre="supervisor")
        s.add_all([pv, rol_sup])
        s.flush()

        rol_alm = Rol(nombre="almacenero")
        # Dos almacenes: el de la sucursal y el central, que no cuelga de
        # ninguna — es el caso que `destinatarios_de_sucursal` no cubre.
        alm_sucursal = Almacen(
            empresa_id=empresa.id, sucursal_id=sucursal.id,
            nombre="Almacén CH1", tipo="sucursal",
        )
        alm_central = Almacen(
            empresa_id=empresa.id, nombre="Central", tipo="central",
        )
        s.add_all([rol_alm, alm_sucursal, alm_central])
        s.flush()

        usuarios = {}
        for nombre in ("cajero", "encargado", "supervisor1", "almacenero1"):
            u = Usuario(username=nombre, pin_hash=hash_pin("654321"), tipo="humano")
            s.add(u)
            s.flush()
            s.add(UsuarioSucursal(usuario_id=u.id, sucursal_id=sucursal.id))
            usuarios[nombre] = u
        s.add(UsuarioRol(usuario_id=usuarios["supervisor1"].id, rol_id=rol_sup.id))
        s.add(UsuarioRol(usuario_id=usuarios["almacenero1"].id, rol_id=rol_alm.id))
        s.commit()
        yield s, {
            "sucursal": sucursal, "pv": pv,
            "alm_sucursal": alm_sucursal, "alm_central": alm_central,
            **usuarios,
        }


def _abrir_caja(s, ids):
    apertura = caja.abrir_caja(
        s,
        punto_venta_id=ids["pv"].id,
        cajero_id=ids["cajero"].id,
        relevo_encargado_id=ids["encargado"].id,
        monto_declarado=Decimal("100.00"),
        detalle_denominaciones={"50": 2},
    )
    s.flush()
    return apertura


# --- Quién es el encargado de turno -----------------------------------------
def test_el_encargado_de_turno_sale_de_la_caja_abierta(env):
    s, ids = env
    _abrir_caja(s, ids)
    assert encargado_de_turno(s, ids["sucursal"].id) == ids["encargado"].id


def test_sin_caja_abierta_no_hay_encargado_de_turno(env):
    s, ids = env
    assert encargado_de_turno(s, ids["sucursal"].id) is None


def test_el_aviso_va_al_encargado_de_turno(env):
    s, ids = env
    _abrir_caja(s, ids)
    assert notificaciones.destinatarios_de_sucursal(s, ids["sucursal"].id) == [
        ids["encargado"].id
    ]


def test_sin_caja_abierta_el_aviso_cae_en_los_supervisores(env):
    s, ids = env
    # Local cerrado o caja sin registrar: avisarle a alguien de más es mejor
    # que perder el aviso.
    assert notificaciones.destinatarios_de_sucursal(s, ids["sucursal"].id) == [
        ids["supervisor1"].id
    ]


def test_una_sucursal_sin_nadie_asignado_no_revienta(env):
    s, ids = env
    otra = Sucursal(
        marca_id=ids["sucursal"].marca_id,
        empresa_id=ids["sucursal"].empresa_id,
        nombre="CH2", direccion="Jr. Y 456", tenencia="alquilada",
    )
    s.add(otra)
    s.flush()
    assert notificaciones.destinatarios_de_sucursal(s, otra.id) == []


# --- Bandeja ----------------------------------------------------------------
def test_notificar_crea_una_fila_por_destinatario(env):
    s, ids = env
    creadas = notificaciones.notificar(
        s,
        [ids["encargado"].id, ids["supervisor1"].id],
        tipo="sales.pedido_demorado",
        titulo="Pedido demorado",
    )
    s.flush()
    assert len(creadas) == 2
    assert len(notificaciones.bandeja(s, ids["encargado"].id)) == 1
    assert len(notificaciones.bandeja(s, ids["supervisor1"].id)) == 1


def test_sin_destinatarios_no_crea_nada_y_no_falla(env):
    s, _ = env
    assert notificaciones.notificar(s, [], tipo="x", titulo="y") == []


def test_marcar_leida_la_saca_de_la_bandeja(env):
    s, ids = env
    (fila,) = notificaciones.notificar(
        s, [ids["encargado"].id], tipo="t", titulo="Título"
    )
    s.flush()

    notificaciones.marcar_leida(s, fila.id, ids["encargado"].id)
    s.flush()
    assert notificaciones.bandeja(s, ids["encargado"].id) == []
    # Sigue existiendo: leída no es borrada.
    assert notificaciones.bandeja(s, ids["encargado"].id, solo_no_leidas=False)


def test_no_se_puede_marcar_leida_la_de_otro(env):
    s, ids = env
    (fila,) = notificaciones.notificar(
        s, [ids["encargado"].id], tipo="t", titulo="Título"
    )
    s.flush()
    assert notificaciones.marcar_leida(s, fila.id, ids["supervisor1"].id) is None
    assert len(notificaciones.bandeja(s, ids["encargado"].id)) == 1


def test_marcar_todas_leidas_solo_toca_las_propias(env):
    s, ids = env
    notificaciones.notificar(s, [ids["encargado"].id] * 3, tipo="t", titulo="T")
    notificaciones.notificar(s, [ids["supervisor1"].id], tipo="t", titulo="T")
    s.flush()

    assert notificaciones.marcar_todas_leidas(s, ids["encargado"].id) == 3
    s.flush()
    assert notificaciones.bandeja(s, ids["encargado"].id) == []
    assert len(notificaciones.bandeja(s, ids["supervisor1"].id)) == 1


# --- El listener ------------------------------------------------------------
def test_el_pedido_demorado_notifica_al_encargado(env, monkeypatch):
    s, ids = env
    _abrir_caja(s, ids)
    s.commit()

    from src.modules.users.application import listeners

    # El listener abre su propia sesión (corre post-commit): se le da la del
    # test para poder inspeccionar el resultado.
    monkeypatch.setattr(
        listeners, "SessionLocal", lambda: _SesionQueNoCierra(s)
    )
    listeners.on_pedido_demorado(
        {
            "venta_id": str(uuid.uuid4()),
            "sucursal_id": str(ids["sucursal"].id),
            "minutos_umbral": 15,
            "minutos_transcurridos": "42.00",
            "estado": "pendiente",
            "items_pendientes": 2,
        }
    )

    (aviso,) = notificaciones.bandeja(s, ids["encargado"].id)
    assert aviso.tipo == "sales.pedido_demorado"
    # `pendiente` = cocina ni lo empezó: alguien tiene que ir, no solo saber.
    assert aviso.nivel == "urgente"
    assert "42" in aviso.titulo
    assert aviso.sucursal_id == ids["sucursal"].id


def test_un_pedido_en_preparacion_avisa_sin_urgencia(env, monkeypatch):
    s, ids = env
    _abrir_caja(s, ids)
    s.commit()

    from src.modules.users.application import listeners

    monkeypatch.setattr(listeners, "SessionLocal", lambda: _SesionQueNoCierra(s))
    listeners.on_pedido_demorado(
        {
            "venta_id": str(uuid.uuid4()),
            "sucursal_id": str(ids["sucursal"].id),
            "minutos_umbral": 15,
            "minutos_transcurridos": "20.00",
            "estado": "en_preparacion",
            "items_pendientes": 1,
        }
    )
    (aviso,) = notificaciones.bandeja(s, ids["encargado"].id)
    assert aviso.nivel == "aviso"


# --- Avisos de inventario ---------------------------------------------------
def test_el_almacen_central_no_tiene_encargado_de_turno_y_avisa_por_rol(env):
    """El caso que `destinatarios_de_sucursal` no cubre: el central no
    cuelga de ninguna sucursal, así que no hay caja abierta que diga quién
    está a cargo. Se resuelve por rol dentro de la empresa."""
    s, ids = env
    destinatarios = notificaciones.destinatarios_de_almacen(
        s, ids["alm_central"].id
    )
    assert set(destinatarios) == {ids["almacenero1"].id, ids["supervisor1"].id}


def test_el_almacen_de_sucursal_suma_al_encargado_de_turno(env):
    s, ids = env
    _abrir_caja(s, ids)
    s.flush()
    destinatarios = notificaciones.destinatarios_de_almacen(
        s, ids["alm_sucursal"].id
    )
    # Los roles de almacén de ESA sucursal, más quien está parado ahí ahora.
    assert set(destinatarios) == {
        ids["almacenero1"].id, ids["supervisor1"].id, ids["encargado"].id
    }


def test_stock_bajo_minimo_avisa_al_almacen(env, monkeypatch):
    s, ids = env
    from src.modules.users.application import listeners

    monkeypatch.setattr(listeners, "SessionLocal", lambda: _SesionQueNoCierra(s))
    sku_id = uuid.uuid4()
    listeners.on_stock_bajo_minimo(
        {
            "almacen_id": str(ids["alm_central"].id),
            "sku_id": str(sku_id),
            "cantidad": "4.0000",
            "stock_minimo": "5.0000",
        }
    )

    avisos = notificaciones.bandeja(s, ids["almacenero1"].id)
    assert len(avisos) == 1
    # Todavía hay stock: lo que falta es reponer, no correr.
    assert avisos[0].nivel == "aviso"
    assert avisos[0].referencia_id == sku_id
    # El central no cuelga de una sucursal: la bandeja no puede inventarle una.
    assert avisos[0].sucursal_id is None


def test_lote_vencido_avisa_con_urgencia(env, monkeypatch):
    """Urgente porque el stock ya se contaba como vendible: alguien pudo
    haberlo servido."""
    s, ids = env
    from src.modules.users.application import listeners

    monkeypatch.setattr(listeners, "SessionLocal", lambda: _SesionQueNoCierra(s))
    lote_id = uuid.uuid4()
    listeners.on_lote_vencido_detectado(
        {
            "lote_id": str(lote_id),
            "almacen_id": str(ids["alm_sucursal"].id),
            "sku_id": str(uuid.uuid4()),
            "fecha_vencimiento": "2026-08-01",
            "cantidad": "3.0000",
        }
    )

    (aviso,) = notificaciones.bandeja(s, ids["almacenero1"].id)
    assert aviso.nivel == "urgente"
    assert aviso.referencia_tipo == "lote"
    assert aviso.sucursal_id == ids["sucursal"].id


def test_conteo_vencido_avisa_al_almacen(env, monkeypatch):
    s, ids = env
    from src.modules.users.application import listeners

    monkeypatch.setattr(listeners, "SessionLocal", lambda: _SesionQueNoCierra(s))
    categoria_id = uuid.uuid4()
    listeners.on_conteo_vencido(
        {
            "almacen_id": str(ids["alm_central"].id),
            "categoria_id": str(categoria_id),
            "categoria": "Perecibles",
            "frecuencia": "diario",
            "fecha_programada": "2026-08-01",
            "dias_atraso": 5,
            "dirigido_a": ["almacen", "gerencia"],
        }
    )

    (aviso,) = notificaciones.bandeja(s, ids["supervisor1"].id)
    assert "Perecibles" in aviso.titulo
    assert aviso.referencia_id == categoria_id


class _SesionQueNoCierra:
    """Envuelve la sesión del test para que el `with` del listener no la
    cierre ni la commitee de verdad — el test necesita seguir leyéndola."""

    def __init__(self, session):
        self._s = session

    def __enter__(self):
        return self._s

    def __exit__(self, *_):
        return False


# --- Aislamiento del bus ----------------------------------------------------
def test_un_listener_que_revienta_no_arrastra_al_publicador():
    """`EventBus` corre los handlers en línea: si uno lanzara hacia arriba,
    una venta fallaría por un fallo de notificación. El aislamiento vive en
    `_despachar`, y esto lo congela."""
    llamados = []

    def revienta(_payload):
        raise RuntimeError("listener roto")

    def sano(payload):
        llamados.append(payload)

    event_bus.subscribe("test.evento_aislado", revienta)
    event_bus.subscribe("test.evento_aislado", sano)
    try:
        # No lanza...
        event_bus.publish("test.evento_aislado", {"x": 1})
        # ...y el handler siguiente igual corrió: un handler roto no puede
        # dejar sin ejecutar a los demás.
        assert llamados == [{"x": 1}]
    finally:
        event_bus._handlers["test.evento_aislado"].clear()


def test_notificacion_referencia_al_hecho_sin_fk(env):
    """`referencia_tipo`/`referencia_id` son polimórficos: la bandeja apunta
    a una venta hoy y a lo que venga mañana, sin ganar una FK por cada tipo."""
    s, ids = env
    venta_id = uuid.uuid4()
    notificaciones.notificar(
        s,
        [ids["encargado"].id],
        tipo="sales.pedido_demorado",
        titulo="T",
        referencia_tipo="venta",
        referencia_id=venta_id,
    )
    s.flush()
    fila = s.scalar(select(Notificacion))
    assert (fila.referencia_tipo, fila.referencia_id) == ("venta", venta_id)
    assert isinstance(fila.created_at, datetime.datetime)
