"""Bus de eventos: despacho inmediato, despacho diferido al commit de la
sesión que publicó, y descarte en rollback."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.core.events import EventBus, event_bus
from src.modules.users.infrastructure.models import Grupo


@pytest.fixture()
def Session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def recibidos(monkeypatch):
    """Deja al bus global con un único handler observable."""
    vistos: list[dict] = []
    monkeypatch.setattr(
        event_bus, "_handlers", {"sales.venta_confirmada": [vistos.append]}
    )
    return vistos


def test_publish_reaches_all_subscribers() -> None:
    bus = EventBus()
    received: list[dict] = []
    bus.subscribe("sales.venta_confirmada", received.append)
    bus.subscribe("sales.venta_confirmada", received.append)

    bus.publish("sales.venta_confirmada", {"venta_id": "v1"})

    assert received == [{"venta_id": "v1"}, {"venta_id": "v1"}]


def test_publish_without_subscribers_is_noop() -> None:
    EventBus().publish("inventory.stock_bajo_minimo", {})


def test_un_handler_que_falla_no_tumba_a_los_demas() -> None:
    """Post-commit ya no hay nada que deshacer: un listener roto se loguea,
    no rompe al emisor ni deja sin evento a los demás suscriptores."""
    bus = EventBus()
    vistos: list[str] = []

    def revienta(_payload: dict) -> None:
        raise RuntimeError("listener roto")

    bus.subscribe("sales.venta_confirmada", revienta)
    bus.subscribe("sales.venta_confirmada", lambda p: vistos.append(p["venta_id"]))

    bus.publish("sales.venta_confirmada", {"venta_id": "v1"})

    assert vistos == ["v1"]


def test_con_sesion_no_despacha_hasta_el_commit(Session, recibidos) -> None:
    with Session() as s:
        s.add(Grupo(nombre="Majambo"))
        s.flush()
        event_bus.publish("sales.venta_confirmada", {"venta_id": "v1"}, session=s)
        assert recibidos == []  # la transacción sigue abierta: todavía nada
        s.commit()

    assert recibidos == [{"venta_id": "v1"}]


def test_rollback_descarta_el_evento(Session, recibidos) -> None:
    """El caso que motivó el diferimiento: si la venta no llega a commitear,
    inventory no debe descontar stock de una venta que no existe."""
    with Session() as s:
        s.add(Grupo(nombre="Majambo"))
        s.flush()
        event_bus.publish("sales.venta_confirmada", {"venta_id": "v1"}, session=s)
        s.rollback()
        s.commit()  # el evento descartado no revive en un commit posterior

    assert recibidos == []


def test_el_handler_ve_lo_que_escribio_el_emisor(Session, monkeypatch) -> None:
    """Despachar post-commit habilita algo que antes no funcionaba: el
    listener abre su propia sesión y encuentra la fila del evento."""
    vistos: list[str | None] = []

    def handler(payload: dict) -> None:
        with Session() as otra:
            vistos.append(
                otra.scalar(select(Grupo.nombre).where(Grupo.nombre == payload["nombre"]))
            )

    monkeypatch.setattr(event_bus, "_handlers", {"sales.venta_confirmada": [handler]})

    with Session() as s:
        s.add(Grupo(nombre="Majambo"))
        s.flush()
        event_bus.publish("sales.venta_confirmada", {"nombre": "Majambo"}, session=s)
        s.commit()

    assert vistos == ["Majambo"]
