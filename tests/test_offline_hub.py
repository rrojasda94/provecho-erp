"""Modo offline del PDV (ADR-009): validación de config del hub y el
detector de conectividad. El motor de sync push/pull es fase 2 — ver ADR."""

import httpx
import pytest

from src.config.settings import Settings
from src.core.sync import estado_conexion

_HUB_OK = {
    "deployment_mode": "hub",
    "hub_empresa_id": "e-1",
    "hub_sucursal_id": "s-1",
    "cloud_sync_url": "https://erp.majambo.pe",
    "cloud_sync_username": "hub_tarapoto",
    "cloud_sync_pin": "123456",
}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**_HUB_OK, **overrides})


# --- Validación de config -----------------------------------------------------
def test_hub_con_config_completa_arranca() -> None:
    s = _settings()
    assert s.es_hub is True


def test_cloud_no_exige_nada_de_hub() -> None:
    assert Settings(_env_file=None).es_hub is False


_CAMPOS_REQUERIDOS = [
    "hub_empresa_id",
    "hub_sucursal_id",
    "cloud_sync_url",
    "cloud_sync_username",
    "cloud_sync_pin",
]


@pytest.mark.parametrize("faltante", _CAMPOS_REQUERIDOS)
def test_hub_incompleto_no_arranca(faltante: str) -> None:
    with pytest.raises(ValueError, match="DEPLOYMENT_MODE=hub requiere"):
        _settings(**{faltante: ""})


def test_deployment_mode_invalido_no_arranca() -> None:
    with pytest.raises(ValueError, match="DEPLOYMENT_MODE debe ser"):
        Settings(_env_file=None, deployment_mode="satelite")


# --- Detector de conectividad --------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_estado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado en memoria del módulo: aislar entre tests."""
    monkeypatch.setattr(estado_conexion, "_estado", estado_conexion.EN_LINEA)
    monkeypatch.setattr(estado_conexion, "_fallos_consecutivos", 0)
    monkeypatch.setattr(estado_conexion, "_ultima_conexion_ok", None)


def test_ping_exitoso_mantiene_en_linea(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(estado_conexion, "_pingar", lambda: True)
    resultado = estado_conexion.verificar_conectividad()
    assert resultado["estado"] == estado_conexion.EN_LINEA
    assert resultado["fallos_consecutivos"] == 0


def test_un_solo_fallo_no_declara_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un timeout puntual de red no puede tumbar el estado — se pide una
    racha, no un solo fallo (SYNC_FALLOS_PARA_OFFLINE)."""
    monkeypatch.setattr(estado_conexion, "_pingar", lambda: False)
    resultado = estado_conexion.verificar_conectividad()
    assert resultado["estado"] == estado_conexion.EN_LINEA
    assert resultado["fallos_consecutivos"] == 1


def test_racha_de_fallos_declara_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(estado_conexion, "_pingar", lambda: False)
    for _ in range(3):
        resultado = estado_conexion.verificar_conectividad()
    assert resultado["estado"] == estado_conexion.OFFLINE
    assert resultado["fallos_consecutivos"] == 3


def test_un_exito_saca_del_offline_de_inmediato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(estado_conexion, "_pingar", lambda: False)
    for _ in range(3):
        estado_conexion.verificar_conectividad()
    assert estado_conexion.estado_actual()["estado"] == estado_conexion.OFFLINE

    monkeypatch.setattr(estado_conexion, "_pingar", lambda: True)
    resultado = estado_conexion.verificar_conectividad()
    assert resultado["estado"] == estado_conexion.EN_LINEA
    assert resultado["fallos_consecutivos"] == 0


def test_pingar_usa_health_liveness_de_la_nube(monkeypatch: pytest.MonkeyPatch) -> None:
    """No debe pegarle a /health/ready: liveness es lo único que un hub
    necesita para saber si la nube responde en absoluto."""
    llamadas = []

    class _RespuestaFalsa:
        def raise_for_status(self):
            pass

    class _ClienteFalso:
        def get(self, url, **kwargs):
            llamadas.append(url)
            return _RespuestaFalsa()

    monkeypatch.setattr(estado_conexion, "_client", _ClienteFalso())
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "cloud_sync_url", "https://erp.majambo.pe/")
    assert estado_conexion._pingar() is True
    assert llamadas == ["https://erp.majambo.pe/health"]


def test_pingar_atrapa_error_de_red(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ClienteRoto:
        def get(self, url, **kwargs):
            raise httpx.ConnectError("sin ruta a la nube")

    monkeypatch.setattr(estado_conexion, "_client", _ClienteRoto())
    assert estado_conexion._pingar() is False


def test_estado_actual_sin_conexion_previa_no_falla() -> None:
    assert estado_conexion.estado_actual()["segundos_desde_ultima_conexion"] is None


# --- Endpoint /health/sync -----------------------------------------------------
def test_health_sync_en_modo_cloud_dice_que_no_aplica(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from src.config import settings as modulo_settings
    from src.core.app import create_app

    monkeypatch.setattr(modulo_settings.settings, "deployment_mode", "cloud")
    respuesta = TestClient(create_app()).get("/health/sync")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"aplica": False, "motivo": "deployment_mode=cloud"}


def test_health_sync_en_hub_offline_sigue_devolviendo_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offline no es un fallo del hub — es su modo de diseño durante un
    corte. Sacarlo de rotación por esto sería contraproducente."""
    from fastapi.testclient import TestClient

    from src.config import settings as modulo_settings
    from src.core.app import create_app

    monkeypatch.setattr(modulo_settings.settings, "deployment_mode", "hub")
    monkeypatch.setattr(estado_conexion, "_pingar", lambda: False)
    monkeypatch.setattr(estado_conexion, "_fallos_consecutivos", 10)
    monkeypatch.setattr(estado_conexion, "_estado", estado_conexion.OFFLINE)

    respuesta = TestClient(create_app()).get("/health/sync")
    assert respuesta.status_code == 200
    assert respuesta.json()["aplica"] is True
    assert respuesta.json()["estado"] == estado_conexion.OFFLINE
