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
import sqlite3
import uuid
from decimal import Decimal

import pytest
from argon2 import PasswordHasher
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.config.settings import settings
from src.modules.users.infrastructure import security


@event.listens_for(Engine, "connect")
def _sqlite_con_fk(conexion_dbapi, _record) -> None:
    """Enciende las FK en cualquier engine SQLite del proceso.

    SQLite las trae apagadas y Postgres no las apaga nunca: sin esto el suite
    deja pasar borrados que dejan al hijo apuntando a un padre que ya no
    existe, y el error aparece recién en producción. Pasó de verdad — anular
    un plato con extras violaba `fk_venta_item_padre` (`NO ACTION`) contra
    Postgres durante meses con las 900 pruebas en verde, porque `anular_lineas`
    borraba el padre antes que los hijos.

    Va sobre la clase `Engine` y no sobre un engine puntual porque cada
    archivo de test arma el suyo con `create_engine("sqlite://")` — son ~75
    fixtures, y una que se olvide del PRAGMA vuelve a abrir el agujero.
    `isinstance` y no la URL: es el driver el que entiende el PRAGMA, y a
    psycopg la sentencia lo haría reventar.
    """
    if isinstance(conexion_dbapi, sqlite3.Connection):
        conexion_dbapi.execute("PRAGMA foreign_keys=ON")


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
    pasan por el endpoint real, con su conteo por denominación.
    """
    from src.modules.accounting.infrastructure.models import AperturaCaja

    apertura = AperturaCaja(
        punto_venta_id=punto_venta_id,
        cajero_id=cajero_id,
        # NULL es lo que escribe la apertura real desde ADR-049: el cajero
        # abre solo y nadie firma. `encargado_id` sigue disponible para los
        # tests que necesitan un encargado de turno derivable de la caja.
        relevo_encargado_id=encargado_id,
        monto_apertura=Decimal(monto),
        detalle_denominaciones=billetes(monto) or None,
    )
    session.add(apertura)
    session.flush()
    return apertura


def auth_headers(session, username: str = "admin") -> dict[str, str]:
    """Cabecera `Authorization` sin pasar por `POST /auth/login`.

    El token que emite es el mismo que emitiría el login —mismos claims,
    misma firma—; lo que se saltea es la verificación del PIN, que ya tiene
    sus propios tests en `test_users_auth.py`.

    Existe para los tests que necesitan **varias identidades distintas** (el
    CRUD de organización compara lo que ve un superusuario con lo que ve un
    admin de una sola empresa): cada login gasta cuota del limiter, que
    desde `_rate_limit_en_memoria` se ejercita de verdad y son 10 por
    ventana. El costo del KDF ya no es el problema —lo resolvió
    `_argon2_barato`—, la cuota sí.
    """
    from src.modules.users.application.auth import build_claims
    from src.modules.users.infrastructure.repositories import UsuarioRepo
    from src.modules.users.infrastructure.security import create_access_token

    usuario = UsuarioRepo(session).get_by_username(username)
    assert usuario is not None, f"usuario '{username}' no existe en la base de prueba"
    token = create_access_token(build_claims(session, usuario))
    return {"Authorization": f"Bearer {token}"}


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


#: Todo módulo que abre su propia sesión fuera del request: los listeners
#: reaccionan a un evento **después** del commit, cuando la sesión del request
#: ya se cerró, y los barridos de Celery ni siquiera corren en un request.
MODULOS_CON_SESSION_FACTORY = (
    "src.modules.accounting.application.listeners",
    "src.modules.inventory.application.listeners",
    "src.modules.marketing.application.listeners",
    # `reports` se suscribe a trece eventos de cuatro módulos y `users`
    # consume el `reports.reporte_emitido` que sale de ahí: entre los dos
    # despiertan en casi cualquier test que confirme una venta o cierre una
    # caja (ADR-033).
    "src.modules.reports.application.listeners",
    "src.modules.users.application.listeners",
    # Los barridos (Celery beat y el cron de la purga). Los ejercitan
    # `test_lotes`, `test_conteos`, `test_inventory`, `test_offline_hub` y
    # `test_alerta_pedido`, que hasta ahora los dejaban abrir la base de
    # producción: 5 s de `connect_timeout` regalados por test y, con la base
    # de desarrollo levantada, el barrido corriendo **contra ella**.
    "src.modules.inventory.application.tasks",
    "src.modules.marketing.application.tasks",
    "src.modules.rrhh.purga",
    "src.modules.sales.application.tasks",
)


@pytest.fixture(autouse=True)
def _listeners_sin_base_real(monkeypatch):
    """Nada que corra fuera del request abre la sesión de producción en un test.

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
            "Se abrió la sesión de producción fuera de un request. El `env` de "
            "este test tiene que parchear el `session_factory` del listener o "
            "del barrido — ver MODULOS_CON_SESSION_FACTORY en tests/conftest.py."
        )

    for nombre in MODULOS_CON_SESSION_FACTORY:
        monkeypatch.setattr(importlib.import_module(nombre), "session_factory", _sin_base_real)


@pytest.fixture(autouse=True)
def _sin_token_factiliza_por_defecto(monkeypatch):
    monkeypatch.setattr(settings, "factiliza_token", "")
    # El de consulta va aparte porque **es** otra credencial (otro producto).
    # Sin blanquearlo, un `.env` local con el token real haría que un test
    # olvidado saliera a la red: gastaría cuota de un proveedor pago y traería
    # datos personales de alguien a un artefacto de CI.
    monkeypatch.setattr(settings, "factiliza_consulta_documento_token", "")


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
