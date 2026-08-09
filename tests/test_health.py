"""Chequeos de salud: liveness, readiness y frescura de backups.

El ERP no alerta por su cuenta — expone estado para que un monitor externo
avise. Lo que se prueba acá es que ese estado sea fiel.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import redis
from fastapi.testclient import TestClient

from src.core import health
from src.core.app import create_app


# --- Liveness ----------------------------------------------------------------
def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "provecho"


def test_liveness_no_depende_de_la_base_de_datos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si liveness fallara por la base, el orquestador reiniciaría en bucle
    un proceso que está perfectamente sano."""
    monkeypatch.setattr(health, "revisar_base_datos", lambda: health._resultado(health.CAIDO))
    assert TestClient(create_app()).get("/health").status_code == 200


# --- Agregación de estados ---------------------------------------------------
@pytest.mark.parametrize(
    ("estados", "esperado"),
    [
        ((health.OK, health.OK), health.OK),
        ((health.OK, health.DEGRADADO), health.DEGRADADO),
        ((health.DEGRADADO, health.CAIDO), health.CAIDO),
        ((health.CAIDO, health.OK), health.CAIDO),
    ],
)
def test_el_peor_componente_manda(estados: tuple, esperado: str) -> None:
    componentes = {f"c{i}": {"estado": e} for i, e in enumerate(estados)}
    assert health.estado_general(componentes) == esperado


# --- Readiness ---------------------------------------------------------------
def _forzar(monkeypatch: pytest.MonkeyPatch, **estados: str) -> None:
    for componente, estado in estados.items():
        monkeypatch.setattr(
            health, f"revisar_{componente}", lambda e=estado: health._resultado(e)
        )


def test_readiness_ok_con_todo_sano(monkeypatch: pytest.MonkeyPatch) -> None:
    _forzar(monkeypatch, base_datos=health.OK, redis=health.OK, cola=health.OK, worker=health.OK)
    respuesta = TestClient(create_app()).get("/health/ready")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == health.OK


def test_readiness_devuelve_503_sin_base_de_datos(monkeypatch: pytest.MonkeyPatch) -> None:
    """503 es lo que hace que el monitor alerte y el proxy saque el nodo."""
    _forzar(monkeypatch, base_datos=health.CAIDO, redis=health.OK, cola=health.OK, worker=health.OK)
    respuesta = TestClient(create_app()).get("/health/ready")
    assert respuesta.status_code == 503
    assert respuesta.json()["componentes"]["base_datos"]["estado"] == health.CAIDO


def test_redis_caido_degrada_pero_no_saca_de_rotacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin Redis el rate limit falla abierto y los comprobantes esperan,
    pero la caja tiene que poder seguir vendiendo."""
    _forzar(
        monkeypatch,
        base_datos=health.OK,
        redis=health.DEGRADADO,
        cola=health.DEGRADADO,
        worker=health.OK,
    )
    respuesta = TestClient(create_app()).get("/health/ready")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == health.DEGRADADO


def test_readiness_no_filtra_infraestructura(monkeypatch: pytest.MonkeyPatch) -> None:
    """El endpoint es público: no puede regalar hostnames ni errores crudos."""
    _forzar(monkeypatch, base_datos=health.CAIDO, redis=health.OK, cola=health.OK, worker=health.OK)
    cuerpo = TestClient(create_app()).get("/health/ready").text
    for filtracion in ("postgresql", "supabase", "redis://", "Traceback", "password"):
        assert filtracion.lower() not in cuerpo.lower()


# --- Componentes -------------------------------------------------------------
def test_base_de_datos_caida_se_reporta_caido(monkeypatch: pytest.MonkeyPatch) -> None:
    def _explota():
        raise OSError("sin conexión")

    monkeypatch.setattr(health.engine, "connect", _explota)
    assert health.revisar_base_datos()["estado"] == health.CAIDO


def test_redis_caido_se_reporta_degradado(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Caido:
        def ping(self):
            raise redis.RedisError("sin conexión")

    monkeypatch.setattr(health, "_cliente_redis", lambda: _Caido())
    assert health.revisar_redis()["estado"] == health.DEGRADADO


def test_cola_atascada_se_reporta_degradada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una cola que crece y no baja es worker muerto, no tráfico alto."""

    class _Lleno:
        def llen(self, clave):
            return 5000

    monkeypatch.setattr(health, "_cliente_redis", lambda: _Lleno())
    resultado = health.revisar_cola()
    assert resultado["estado"] == health.DEGRADADO
    assert resultado["pendientes"] == 5000


def test_cola_vacia_esta_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Vacio:
        def llen(self, clave):
            return 0

    monkeypatch.setattr(health, "_cliente_redis", lambda: _Vacio())
    assert health.revisar_cola()["estado"] == health.OK


# --- Frescura de backups -----------------------------------------------------
def _backup(directorio: Path, horas_atras: float) -> Path:
    import os

    ruta = directorio / "provecho-20260726-030000.dump"
    ruta.write_bytes(b"PGDMP")
    momento = (datetime.now(UTC) - timedelta(hours=horas_atras)).timestamp()
    os.utime(ruta, (momento, momento))
    return ruta


def test_backup_reciente_esta_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "backup_dir", str(tmp_path))
    _backup(tmp_path, horas_atras=3)
    assert health.revisar_backups()["estado"] == health.OK


def test_backup_viejo_se_reporta_caido(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El caso traicionero: el cron dejó de correr y nadie se entera hasta
    que hace falta restaurar."""
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "backup_dir", str(tmp_path))
    _backup(tmp_path, horas_atras=72)
    resultado = health.revisar_backups()
    assert resultado["estado"] == health.CAIDO
    assert resultado["horas_desde_ultimo"] == pytest.approx(72, abs=1)


def test_sin_ningun_backup_se_reporta_caido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "backup_dir", str(tmp_path))
    assert health.revisar_backups() == {"estado": health.CAIDO, "motivo": "sin_backups"}


def test_directorio_de_backups_inexistente_no_revienta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "backup_dir", str(tmp_path / "no-existe"))
    assert health.revisar_backups()["estado"] == health.CAIDO


def test_endpoint_de_backups_devuelve_503_si_esta_vencido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "backup_dir", str(tmp_path))
    _backup(tmp_path, horas_atras=72)
    assert TestClient(create_app()).get("/health/backups").status_code == 503


def test_los_backups_no_sacan_la_api_de_rotacion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Que falte un backup es grave, pero tumbar el readiness por eso
    dejaría al restaurante sin vender."""
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "backup_dir", str(tmp_path / "vacio"))
    _forzar(monkeypatch, base_datos=health.OK, redis=health.OK, cola=health.OK, worker=health.OK)
    assert TestClient(create_app()).get("/health/ready").status_code == 200


# --- Salud del worker --------------------------------------------------------
def test_worker_sin_latido_se_reporta_degradado(monkeypatch: pytest.MonkeyPatch) -> None:
    """La cola solo delata al worker cuando hay trabajo: con cola vacía, uno
    muerto y uno ocioso se ven igual. El latido los distingue."""

    class _SinLatido:
        def exists(self, clave):
            return 0

    monkeypatch.setattr(health, "_cliente_redis", lambda: _SinLatido())
    resultado = health.revisar_worker()
    assert resultado["estado"] == health.DEGRADADO
    assert resultado["motivo"] == "sin_latido"


def test_worker_con_latido_esta_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ConLatido:
        def exists(self, clave):
            return 1

    monkeypatch.setattr(health, "_cliente_redis", lambda: _ConLatido())
    assert health.revisar_worker()["estado"] == health.OK


def test_worker_degrada_pero_no_saca_de_rotacion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin worker la caja sigue vendiendo: lo que se posterga es el
    comprobante y la alerta de cocina, no la venta."""
    _forzar(
        monkeypatch,
        base_datos=health.OK,
        redis=health.OK,
        cola=health.OK,
        worker=health.DEGRADADO,
    )
    respuesta = TestClient(create_app()).get("/health/ready")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == health.DEGRADADO


def test_el_latido_no_tumba_la_tarea_si_redis_no_responde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Que el worker no pueda anunciarse no es motivo para que la tarea
    falle: el síntoma ya lo recoge el chequeo del otro lado."""

    class _Caido:
        def set(self, *a, **k):
            raise redis.RedisError("sin conexión")

    monkeypatch.setattr(health, "_cliente_redis", lambda: _Caido())
    health.registrar_latido_worker()  # no lanza
