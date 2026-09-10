"""`ruta_optima` contra la Routes API de Google (ADR-098): sin red real,
`httpx.post` queda parcheado. Mismo patrón que `test_factiliza_consulta.py`.
"""

from decimal import Decimal

import httpx
import pytest

from src.config.settings import settings
from src.shared.integrations.google import Coordenada, RutasError, ruta_optima


class _RespuestaFalsa:
    def __init__(self, status_code, cuerpo=None, *, ilegible=False):
        self.status_code = status_code
        self._cuerpo = cuerpo
        self._ilegible = ilegible

    def json(self):
        if self._ilegible:
            raise ValueError("no es JSON")
        return self._cuerpo


ORIGEN = Coordenada(lat=Decimal("-6.487"), lng=Decimal("-76.363"))
PARADA_A = Coordenada(lat=Decimal("-6.490"), lng=Decimal("-76.360"))
PARADA_B = Coordenada(lat=Decimal("-6.485"), lng=Decimal("-76.365"))


@pytest.fixture(autouse=True)
def _con_clave(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_server_key", "clave-de-prueba")


def _respuesta_valida(*, orden=None, legs=None, distancia=5000, duracion="900s", polyline="abc"):
    return {
        "routes": [
            {
                "optimizedIntermediateWaypointIndex": orden,
                "distanceMeters": distancia,
                "duration": duracion,
                "polyline": {"encodedPolyline": polyline},
                "legs": legs
                or [
                    {"distanceMeters": 2000, "duration": "300s"},
                    {"distanceMeters": 2000, "duration": "300s"},
                    {"distanceMeters": 1000, "duration": "300s"},  # vuelta al origen
                ],
            }
        ]
    }


def test_sin_clave_configurada_levanta_rutas_error(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_server_key", "")
    with pytest.raises(RutasError):
        ruta_optima(ORIGEN, [PARADA_A])


def test_ninguna_parada_es_un_error_de_uso():
    with pytest.raises(ValueError):
        ruta_optima(ORIGEN, [])


def test_con_una_sola_parada_no_pide_optimizar_el_orden(monkeypatch):
    capturado = {}

    def _post(url, *, json, headers, timeout):
        capturado["cuerpo"] = json
        return _RespuestaFalsa(
            200,
            _respuesta_valida(
                orden=None,
                legs=[
                    {"distanceMeters": 2000, "duration": "300s"},
                    {"distanceMeters": 2000, "duration": "300s"},
                ],
            ),
        )

    monkeypatch.setattr(httpx, "post", _post)
    ruta_optima(ORIGEN, [PARADA_A])
    assert "optimizeWaypointOrder" not in capturado["cuerpo"]
    assert len(capturado["cuerpo"]["intermediates"]) == 1


def test_con_varias_paradas_pide_optimizar_el_orden(monkeypatch):
    capturado = {}

    def _post(url, *, json, headers, timeout):
        capturado["cuerpo"] = json
        return _RespuestaFalsa(200, _respuesta_valida(orden=[1, 0]))

    monkeypatch.setattr(httpx, "post", _post)
    ruta_optima(ORIGEN, [PARADA_A, PARADA_B])
    assert capturado["cuerpo"]["optimizeWaypointOrder"] is True
    assert capturado["cuerpo"]["destination"] == capturado["cuerpo"]["origin"]


def test_respuesta_con_error_http_levanta_rutas_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _RespuestaFalsa(400))
    with pytest.raises(RutasError):
        ruta_optima(ORIGEN, [PARADA_A])


def test_transporte_caido_levanta_rutas_error(monkeypatch):
    def _explota(*a, **k):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx, "post", _explota)
    with pytest.raises(RutasError):
        ruta_optima(ORIGEN, [PARADA_A])


def test_respuesta_ilegible_levanta_rutas_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _RespuestaFalsa(200, ilegible=True))
    with pytest.raises(RutasError):
        ruta_optima(ORIGEN, [PARADA_A])


def test_sin_rutas_en_la_respuesta_devuelve_none(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _RespuestaFalsa(200, {"routes": []}))
    assert ruta_optima(ORIGEN, [PARADA_A]) is None


def test_cantidad_de_tramos_no_coincide_levanta_rutas_error(monkeypatch):
    # Dos paradas piden 2 tramos + la vuelta = 3 legs; acá solo llegan 2.
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _RespuestaFalsa(
            200, _respuesta_valida(orden=[0, 1], legs=[{"distanceMeters": 1, "duration": "1s"}])
        ),
    )
    with pytest.raises(RutasError):
        ruta_optima(ORIGEN, [PARADA_A, PARADA_B])


def test_ruta_calculada_trae_orden_tramos_y_polilinea(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _RespuestaFalsa(200, _respuesta_valida(orden=[1, 0])),
    )
    calculada = ruta_optima(ORIGEN, [PARADA_A, PARADA_B])
    assert calculada is not None
    assert calculada.orden == [1, 0]
    assert len(calculada.tramos) == 2
    assert calculada.tramos[0].distancia_m == 2000
    assert calculada.tramos[0].duracion_seg == 300
    # El total incluye la vuelta al origen; los tramos de cada parada no.
    assert calculada.distancia_m == 5000
    assert calculada.duracion_seg == 900
    assert calculada.polyline == "abc"


def test_duracion_con_decimales_se_trunca_a_segundos(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _RespuestaFalsa(
            200,
            _respuesta_valida(
                orden=None,
                legs=[{"distanceMeters": 500, "duration": "123.7s"}],
                duracion="123.7s",
            ),
        ),
    )
    calculada = ruta_optima(ORIGEN, [PARADA_A])
    assert calculada.tramos[0].duracion_seg == 123
    assert calculada.duracion_seg == 123


def test_sin_duracion_en_un_tramo_es_cero(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _RespuestaFalsa(
            200,
            _respuesta_valida(orden=None, legs=[{"distanceMeters": 500, "duration": None}]),
        ),
    )
    calculada = ruta_optima(ORIGEN, [PARADA_A])
    assert calculada.tramos[0].duracion_seg == 0
