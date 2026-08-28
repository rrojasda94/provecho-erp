"""Borrador del PDV del lado del servidor (ADR-074).

El ticket a medio armar vivía solo en la memoria del navegador: recargar la
página, quedarse sin batería o cambiar de turno borraba las pestañas de
pedido y el mesero volvía a teclear la mesa entera.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.sales.application import borradores as borradores_uc
from src.modules.sales.application.errors import NoEncontrado
from src.modules.sales.infrastructure.models import PedidoBorrador, PuntoVenta
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Sucursal,
    Usuario,
)
from src.shared import fechas

TICKET = {
    "tipo": "mesa",
    "mesaId": "7",
    "comensales": 4,
    "lineas": [{"producto": "Pizza Clásica", "cantidad": "2"}],
}


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    event.listen(
        engine,
        "connect",
        lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def base(session):
    grupo = Grupo(nombre="Grupo Majambo")
    session.add(grupo)
    session.flush()
    empresa = Empresa(
        grupo_id=grupo.id,
        razon_social="Majambo EIRL",
        ruc="20450311520",
        domicilio_fiscal="Tarapoto",
        tipo="operativa",
        zona_tributaria="amazonia_ley27037",
    )
    marca = Marca(grupo_id=grupo.id, nombre="Charlie's Pizzas", tipo="restaurante")
    session.add_all([empresa, marca])
    session.flush()
    sucursal = Sucursal(
        marca_id=marca.id,
        empresa_id=empresa.id,
        nombre="Charlie's - Plaza",
        direccion="Jr. Ejemplo 123",
        tenencia="propia",
    )
    session.add(sucursal)
    session.flush()
    caja = PuntoVenta(
        sucursal_id=sucursal.id,
        canal="trabajador",
        serie_boleta="B001",
        serie_factura="F001",
        politica_pago="al_finalizar",
    )
    otra_caja = PuntoVenta(
        sucursal_id=sucursal.id,
        canal="trabajador",
        serie_boleta="B002",
        serie_factura="F002",
        politica_pago="al_finalizar",
    )
    turno_dia = Usuario(username="ana.dia", pin_hash="fake", tipo="humano")
    turno_noche = Usuario(username="beto.noche", pin_hash="fake", tipo="humano")
    session.add_all([caja, otra_caja, turno_dia, turno_noche])
    session.flush()
    return {
        "caja": caja,
        "otra_caja": otra_caja,
        "turno_dia": turno_dia,
        "turno_noche": turno_noche,
    }


def _guardar(session, base, contenido=None, borrador_id=None, usuario=None, caja=None):
    return borradores_uc.guardar(
        session,
        borrador_id=borrador_id or uuid.uuid4(),
        punto_venta_id=(caja or base["caja"]).id,
        contenido=contenido if contenido is not None else dict(TICKET),
        usuario_id=(usuario or base["turno_dia"]).id,
    )


def test_el_borrador_sobrevive_a_la_recarga(session, base):
    guardado = _guardar(session, base)
    session.expire_all()

    vivos = borradores_uc.listar(session, punto_venta_id=base["caja"].id)
    assert [b.id for b in vivos] == [guardado.id]
    assert vivos[0].contenido == TICKET


def test_guardar_dos_veces_el_mismo_id_no_apila_pestanas(session, base):
    """El navegador guarda con cada cambio y no lleva la cuenta de si esta
    pestaña ya llegó al servidor: mandar siempre el mismo `PUT` tiene que
    dejar el mismo estado, no una pestaña nueva por tecla."""
    borrador_id = uuid.uuid4()
    _guardar(session, base, borrador_id=borrador_id)
    _guardar(
        session, base, borrador_id=borrador_id, contenido={**TICKET, "comensales": 6}
    )

    vivos = borradores_uc.listar(session, punto_venta_id=base["caja"].id)
    assert len(vivos) == 1
    assert vivos[0].contenido["comensales"] == 6


def test_el_borrador_es_de_la_caja_y_lo_sigue_el_relevo(session, base):
    """Por punto de venta y no por usuario: el turno de la noche tiene que
    poder seguir el pedido que dejó el de la tarde sin que este cierre
    sesión primero."""
    borrador_id = uuid.uuid4()
    _guardar(session, base, borrador_id=borrador_id, usuario=base["turno_dia"])
    _guardar(
        session,
        base,
        borrador_id=borrador_id,
        usuario=base["turno_noche"],
        contenido={**TICKET, "comensales": 2},
    )

    vivos = borradores_uc.listar(session, punto_venta_id=base["caja"].id)
    assert len(vivos) == 1
    # Quién lo tocó al final, no quién lo abrió.
    assert vivos[0].usuario_id == base["turno_noche"].id


def test_la_caja_de_al_lado_no_ve_el_borrador(session, base):
    _guardar(session, base, caja=base["caja"])

    assert borradores_uc.listar(session, punto_venta_id=base["otra_caja"].id) == []


def test_descartar_es_idempotente(session, base):
    """El PDV descarta al enviar el pedido y al cerrar la pestaña, dos
    caminos que pueden cruzarse. Borrar dos veces no puede ser un error."""
    guardado = _guardar(session, base)

    borradores_uc.descartar(session, guardado.id)
    borradores_uc.descartar(session, guardado.id)

    assert borradores_uc.listar(session, punto_venta_id=base["caja"].id) == []


def test_guardar_contra_una_caja_que_no_existe_falla(session, base):
    with pytest.raises(NoEncontrado):
        borradores_uc.guardar(
            session,
            borrador_id=uuid.uuid4(),
            punto_venta_id=uuid.uuid4(),
            contenido=TICKET,
            usuario_id=base["turno_dia"].id,
        )


def test_lo_que_quedo_de_ayer_no_vuelve_a_la_pantalla(session, base):
    """Un borrador sin enviar de un turno que ya cerró no es un pedido que
    alguien esté esperando: devolverlo llenaría el PDV de pestañas que nadie
    va a cobrar."""
    viejo = _guardar(session, base)
    viejo.created_at = fechas.inicio_dia_utc(fechas.hoy()) - timedelta(hours=3)
    session.flush()
    de_hoy = _guardar(session, base)

    vivos = borradores_uc.listar(session, punto_venta_id=base["caja"].id)
    assert [b.id for b in vivos] == [de_hoy.id]


def test_purgar_borra_los_de_jornadas_anteriores(session, base):
    """`listar` deja de mostrarlos; esto es lo que evita que la tabla crezca
    sin techo con el ticket a medio armar de cada turno del año."""
    viejo = _guardar(session, base)
    viejo.created_at = fechas.inicio_dia_utc(fechas.hoy()) - timedelta(days=2)
    session.flush()
    de_hoy = _guardar(session, base)

    assert borradores_uc.purgar(session) == 1
    # `expunge_all` y no `expire_all`: el borrado lo hizo la base sin
    # sincronizar la sesión, así que `get` sobre la instancia cacheada
    # levantaría `ObjectDeletedError` en vez de devolver `None`.
    session.expunge_all()
    assert session.get(PedidoBorrador, viejo.id) is None
    assert session.get(PedidoBorrador, de_hoy.id) is not None


def test_el_contenido_es_opaco_para_el_servidor(session, base):
    """El borrador todavía no es un hecho de negocio: no descuenta stock, no
    asienta y no se cobra. Lo que sale a cocina sí se valida entero, en
    `crear_venta`."""
    a_medio_armar = {"tipo": None, "lineas": [], "notaLibre": "sin cebolla"}
    guardado = _guardar(session, base, contenido=a_medio_armar)
    session.expire_all()

    assert session.get(PedidoBorrador, guardado.id).contenido == a_medio_armar


def test_el_borrador_hereda_la_sucursal_de_su_caja(session, base):
    """El alcance de tenant se valida contra la sucursal, y esa no la manda
    el cliente: sale del punto de venta (ADR-004)."""
    guardado = _guardar(session, base)

    assert guardado.sucursal_id == base["caja"].sucursal_id


def test_el_decimal_del_ticket_viaja_como_texto(session, base):
    """Recordatorio de contrato: `contenido` es JSON, así que los montos van
    como texto. Guardar un `Decimal` crudo reventaría al serializar, y este
    test es el que lo dice antes de que lo diga producción."""
    guardado = _guardar(
        session, base, contenido={"lineas": [{"precio": str(Decimal("25.50"))}]}
    )
    session.expire_all()

    assert session.get(PedidoBorrador, guardado.id).contenido == {
        "lineas": [{"precio": "25.50"}]
    }
