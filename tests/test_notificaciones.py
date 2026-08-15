"""La bandeja: qué guarda, quién la lee y qué la llena.

**A quién le llega cada aviso ya no se decide acá.** Desde 2026-08-08 eso es
`reports` (ADR-033) y sus tests viven en `tests/test_reports.py`: la
resolución de destinatarios, los resolutores dinámicos y la emisión por
evento se probaron acá mientras `users` era el dueño de esa regla.

Lo que queda es lo que `users` sigue siendo dueño: la tabla `notificacion`,
su lectura, y el único listener que la llena a partir de un
`reports.reporte_emitido` ya resuelto.
"""

import datetime
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.core.events import event_bus
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
from tests.conftest import abrir_caja_directa


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


def _abrir_caja(s, ids, *, con_encargado=False):
    """Turno de caja abierto.

    Con `con_encargado=True` se escribe `relevo_encargado_id`, que es lo que
    dejaban las aperturas **anteriores a ADR-048**, cuando abrir exigía la
    firma del encargado. Filas así siguen existiendo en cualquier base que
    ya haya operado, y `encargado_de_turno` tiene que saber leerlas.
    """
    apertura = abrir_caja_directa(
        s,
        punto_venta_id=ids["pv"].id,
        cajero_id=ids["cajero"].id,
        encargado_id=ids["encargado"].id if con_encargado else None,
        monto="100.00",
    )
    s.flush()
    return apertura


# --- Quién es el encargado de turno -----------------------------------------
def test_el_encargado_de_turno_sale_de_la_caja_abierta(env):
    """Aperturas viejas: el encargado firmó y ahí quedó quién estaba a cargo."""
    s, ids = env
    _abrir_caja(s, ids, con_encargado=True)
    assert encargado_de_turno(s, ids["sucursal"].id) == ids["encargado"].id


def test_una_apertura_nueva_no_deja_encargado_de_turno(env):
    """Desde ADR-048 el cajero abre solo, así que la caja abierta ya no dice
    quién está a cargo del local.

    No se sustituye por el cajero: avisarle a él de algo que él no puede
    resolver es peor que decir que no se sabe y dejar que el respaldo por rol
    haga su trabajo (`test_reports.py`).
    """
    s, ids = env
    _abrir_caja(s, ids)
    assert encargado_de_turno(s, ids["sucursal"].id) is None


def test_sin_caja_abierta_no_hay_encargado_de_turno(env):
    s, ids = env
    assert encargado_de_turno(s, ids["sucursal"].id) is None


# A quién se le avisa a partir de ese encargado se prueba en
# `tests/test_reports.py::test_el_aviso_va_al_encargado_de_turno` y vecinos.


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
def test_un_reporte_emitido_llena_la_bandeja_de_cada_destinatario(env, monkeypatch):
    """`reports` ya resolvió a quién: acá solo se reparte.

    La notificación apunta al **reporte**, no al hecho original — el reporte
    ya guarda esa referencia junto con su foto de datos, así que apuntar ahí
    es apuntar a todo.
    """
    s, ids = env
    from src.modules.users.application import listeners

    # El listener abre su propia sesión (corre post-commit): se le da la del
    # test para poder inspeccionar el resultado.
    monkeypatch.setattr(
        listeners, "session_factory", lambda: _SesionQueNoCierra(s)
    )
    reporte_id = uuid.uuid4()
    listeners.on_reporte_emitido(
        {
            "reporte_emitido_id": str(reporte_id),
            "codigo": "sales.pedido_demorado",
            "titulo": "Pedido demorado: 42 min (umbral 15)",
            "cuerpo": "Estado pendiente, 2 ítem(s) pendiente(s).",
            "nivel": "urgente",
            "sucursal_id": str(ids["sucursal"].id),
            "referencia_tipo": "venta",
            "referencia_id": str(uuid.uuid4()),
            "destinatarios": [
                str(ids["encargado"].id),
                str(ids["supervisor1"].id),
            ],
        }
    )

    (aviso,) = notificaciones.bandeja(s, ids["encargado"].id)
    # `tipo` sigue siendo el código de la emisión: es por lo que el frontend
    # agrupa e iconiza, y eso no cambió al mudar la decisión de destinatario.
    assert aviso.tipo == "sales.pedido_demorado"
    assert aviso.nivel == "urgente"
    assert "42" in aviso.titulo
    assert aviso.sucursal_id == ids["sucursal"].id
    assert (aviso.referencia_tipo, aviso.referencia_id) == (
        "reporte_emitido",
        reporte_id,
    )
    assert len(notificaciones.bandeja(s, ids["supervisor1"].id)) == 1


def test_un_reporte_sin_destinatarios_no_crea_bandeja(env, monkeypatch):
    """El hueco se registra del lado de `reports` (RN-REP-005). Acá no hay
    nada que repartir, y pedir la sesión para no escribir nada sería abrir
    una transacción por cada hecho que no le llega a nadie."""
    s, ids = env
    from src.modules.users.application import listeners

    def _explota():
        raise AssertionError("no debería abrir sesión sin destinatarios")

    monkeypatch.setattr(listeners, "session_factory", _explota)
    listeners.on_reporte_emitido(
        {
            "reporte_emitido_id": str(uuid.uuid4()),
            "codigo": "sales.venta_anulada",
            "titulo": "Venta anulada",
            "nivel": "aviso",
            "destinatarios": [],
        }
    )
    assert notificaciones.bandeja(s, ids["encargado"].id) == []


def test_un_reporte_de_ambito_empresa_no_inventa_sucursal(env, monkeypatch):
    """Un pago sobre umbral es de la empresa: la bandeja no puede colgarlo
    de un local que el hecho nunca tuvo."""
    s, ids = env
    from src.modules.users.application import listeners

    monkeypatch.setattr(listeners, "session_factory", lambda: _SesionQueNoCierra(s))
    listeners.on_reporte_emitido(
        {
            "reporte_emitido_id": str(uuid.uuid4()),
            "codigo": "accounting.pago_requiere_aprobacion",
            "titulo": "Pago de 5000 espera aprobación (umbral 2000)",
            "nivel": "aviso",
            "sucursal_id": None,
            "destinatarios": [str(ids["supervisor1"].id)],
        }
    )
    (aviso,) = notificaciones.bandeja(s, ids["supervisor1"].id)
    assert aviso.sucursal_id is None


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
