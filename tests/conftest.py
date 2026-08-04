"""Fixtures compartidas por todo el suite.

Autouse: ningún test debe golpear una API externa real solo porque el
`.env` local tiene un token cargado (Factiliza, RUC/DNI). Los tests que sí
necesitan probar la integración fijan su propio token+mock explícitamente
(ver test_facturacion_electronica.py).

También viven acá los dos ayudantes de caja, porque desde que **no se cobra
sin caja abierta** (RN-MDP-002) cualquier test que registre un pago necesita
un turno abierto.
"""

import uuid
from decimal import Decimal

import pytest

from src.config.settings import settings

DENOMINACIONES = (
    "200", "100", "50", "20", "10", "5", "2", "1", "0.50", "0.20", "0.10",
)


def billetes(monto: str | Decimal) -> dict[str, int]:
    """Descompone un monto en billetes y monedas (mayor a menor).

    La apertura y el cierre exigen el conteo por denominación (RN-POS-003/007)
    y de ahí sale el monto; tipear el desglose en cada test sería ruido.
    """
    resto = Decimal(str(monto))
    detalle: dict[str, int] = {}
    for d in DENOMINACIONES:
        valor = Decimal(d)
        cantidad = int(resto // valor)
        if cantidad:
            detalle[d] = cantidad
            resto -= valor * cantidad
    assert resto == 0, f"monto no descomponible en denominaciones: {monto}"
    return detalle


def abrir_caja_directa(
    session,
    *,
    punto_venta_id: uuid.UUID,
    cajero_id: uuid.UUID,
    encargado_id: uuid.UUID | None = None,
    monto: str = "0.00",
):
    """Turno de caja insertado directo, para tests que no prueban la caja.

    Los que sí la prueban (`test_caja_ciclo.py`, `test_dashboard_caja.py`)
    pasan por el endpoint real, con su elevación de PIN y su conteo.
    """
    from src.modules.accounting.infrastructure.models import AperturaCaja

    apertura = AperturaCaja(
        punto_venta_id=punto_venta_id,
        cajero_id=cajero_id,
        # Sin encargado propio se reusa el cajero: la FK tiene que apuntar a
        # un usuario real, y estos tests no prueban el relevo.
        relevo_encargado_id=encargado_id or cajero_id,
        monto_apertura=Decimal(monto),
        detalle_denominaciones=billetes(monto) or None,
    )
    session.add(apertura)
    session.flush()
    return apertura


@pytest.fixture(autouse=True)
def _sin_token_factiliza_por_defecto(monkeypatch):
    monkeypatch.setattr(settings, "factiliza_token", "")


@pytest.fixture(autouse=True)
def _cola_en_memoria(monkeypatch):
    """Mismo criterio que el token: ningún test habla con un broker real.

    El `.env` local apunta a `redis://redis:6379` — el hostname del servicio
    en Docker, que fuera de Docker **no resuelve**. Cada `apply_async` pagaba
    una resolución DNS fallida de varios segundos, y como el listener de
    alertas encola en cada venta confirmada, el suite pasó de ~5 a 63
    minutos. `memory://` es el transporte en proceso de kombu: encola de
    verdad (la tarea no se pierde ni se ejecuta sola), sin tocar la red.
    """
    from src.core.celery_app import celery_app

    monkeypatch.setattr(settings, "celery_broker_url", "memory://")
    monkeypatch.setitem(celery_app.conf, "broker_url", "memory://")
    monkeypatch.setitem(celery_app.conf, "result_backend", "cache+memory://")
