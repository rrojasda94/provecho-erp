"""Fixtures compartidas por todo el suite.

Autouse: ningún test debe golpear una API externa real solo porque el
`.env` local tiene un token cargado (Factiliza, RUC/DNI). Los tests que sí
necesitan probar la integración fijan su propio token+mock explícitamente
(ver test_facturacion_electronica.py).

También viven acá los dos ayudantes de caja, porque desde que **no se cobra
sin caja abierta** (RN-MDP-002) cualquier test que registre un pago necesita
un turno abierto.
"""

import importlib
import uuid
from decimal import Decimal

import pytest
from argon2 import PasswordHasher

from src.config.settings import settings
from src.modules.users.infrastructure import security

#: Los parámetros reales del hasher, antes de abaratarlos para el suite.
#: `test_security.py` verifica que sigan por encima del piso recomendado.
HASHER_PRODUCCION = security._hasher

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


class RedisFalso:
    """Contador en memoria con la superficie que usa el limiter."""

    def __init__(self) -> None:
        self.claves: dict[str, int] = {}

    def incr(self, clave: str) -> int:
        self.claves[clave] = self.claves.get(clave, 0) + 1
        return self.claves[clave]

    def expire(self, clave: str, segundos: int) -> None:
        pass


@pytest.fixture(autouse=True, scope="session")
def _argon2_barato():
    """Argon2id calibrado para producción cuesta ~55 ms por hash.

    El seeder hashea el PIN del admin y casi todo test de API hace un login,
    así que el suite pagaba ~25% de su tiempo en KDF. Acá solo importa que
    un hash verifique contra su PIN, no que sea caro de romper: los
    parámetros de verdad viven en `security._hasher` y los cuida
    `test_seguridad_del_hasher_de_produccion`.
    """
    security._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    yield
    security._hasher = HASHER_PRODUCCION


@pytest.fixture(autouse=True)
def _rate_limit_en_memoria(monkeypatch):
    """Mismo criterio que el broker: el limiter no habla con un Redis real.

    Sin esto cada login pagaba un intento de conexión rechazado (~17 ms) y el
    límite quedaba fail-open, o sea nunca se ejercitaba. El contador es nuevo
    en cada test para que las cuotas (10 logins/min) no se arrastren de uno
    a otro.
    """
    from src.core import rate_limit

    monkeypatch.setattr(rate_limit, "_client", RedisFalso())
    monkeypatch.setattr(rate_limit, "_reintentar_desde", 0.0)


#: Los tres módulos de listeners que abren su propia sesión: reaccionan a un
#: evento **después** del commit, cuando la sesión del request ya se cerró.
MODULOS_CON_SESSION_FACTORY = (
    "src.modules.accounting.application.listeners",
    "src.modules.inventory.application.listeners",
    "src.modules.marketing.application.listeners",
)


@pytest.fixture(autouse=True)
def _listeners_sin_base_real(monkeypatch):
    """Ningún listener puede abrir la sesión de producción durante un test.

    Cada `env` parchea el `session_factory` de los listeners que su test
    ejercita, pero **solo esos**. Los demás quedaban apuntando al Postgres
    real: confirmar una venta despertaba `accounting.on_venta_confirmada`, que
    abría su propia sesión y se quedaba en `psycopg.wait_conn` — sin timeout,
    o sea para siempre. Así se colgaba el suite entero, y con la base de
    desarrollo levantada era peor: el test escribía asientos en ella.

    Reemplazarlo por algo que revienta es seguro: `EventBus._despachar` ya
    atrapa y registra lo que falle en un handler (un fallo de inventario nunca
    cancela la venta). El test que sí necesite el listener lo parchea, como
    hasta ahora; el que no, ve el error en el log en vez de colgarse.
    """

    def _sin_base_real():
        raise RuntimeError(
            "El listener abrió la sesión de producción. El `env` de este test "
            "tiene que parchear su `session_factory` — ver "
            "MODULOS_CON_SESSION_FACTORY en tests/conftest.py."
        )

    for nombre in MODULOS_CON_SESSION_FACTORY:
        monkeypatch.setattr(importlib.import_module(nombre), "session_factory", _sin_base_real)


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
