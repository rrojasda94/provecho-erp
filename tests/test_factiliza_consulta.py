"""Consulta RUC/DNI contra Factiliza (RENIEC/SUNAT vía el mismo proveedor,
RN-PTS-004 addendum 2026-08-02). Nunca toca la red: `httpx.get` se
reemplaza por un doble.
"""

import httpx
import pytest

from src.shared.integrations.factiliza import nombres_desde_dni, razon_social_desde_ruc
from src.shared.integrations.factiliza.client import (
    ConsultaEmpresa,
    ConsultaPersona,
    FactilizaClient,
    FactilizaError,
)


class _RespuestaFalsa:
    def __init__(self, status_code, texto, cuerpo=None):
        self.status_code = status_code
        self.text = texto
        self._cuerpo = cuerpo

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin cuerpo")
        return self._cuerpo


def test_consultar_dni_encontrado(monkeypatch):
    cuerpo = {
        "success": True,
        "data": {
            "numero": "73632127",
            "nombres": "CARLOS RENATO",
            "apellido_paterno": "ROJAS",
            "apellido_materno": "DEL AGUILA",
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = FactilizaClient(token="t").consultar_dni("73632127")
    assert r == ConsultaPersona(True, "73632127", "CARLOS RENATO", "ROJAS DEL AGUILA", cuerpo)


def test_consultar_ruc_encontrado(monkeypatch):
    cuerpo = {
        "success": True,
        "data": {
            "numero": "20610077782",
            "nombre_o_razon_social": "SERVICIOS RENTAURANT S.A.C",
            "estado": "BAJA DE OFICIO",
            "condicion": "HABIDO",
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = FactilizaClient(token="t").consultar_ruc("20610077782")
    assert r == ConsultaEmpresa(
        True, "20610077782", "SERVICIOS RENTAURANT S.A.C", "BAJA DE OFICIO", "HABIDO", cuerpo
    )


def test_consultar_dni_no_encontrado_404_vacio_no_es_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(404, ""))
    r = FactilizaClient(token="t").consultar_dni("00000000")
    assert r.encontrado is False


def test_consultar_sin_token_configurado_lanza_factiliza_error():
    with pytest.raises(FactilizaError):
        FactilizaClient(token="").consultar_dni("73632127")


def test_nombres_desde_dni_hace_fallback_si_factiliza_falla(monkeypatch):
    def explota(self, dni):
        raise FactilizaError("caído")

    monkeypatch.setattr(FactilizaClient, "consultar_dni", explota)
    assert nombres_desde_dni("73632127", "Tecleado", "Apellido") == ("Tecleado", "Apellido")


def test_nombres_desde_dni_hace_fallback_si_no_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_dni",
        lambda self, dni: ConsultaPersona(False, dni, "", "", {}),
    )
    assert nombres_desde_dni("73632127", "Tecleado", "Apellido") == ("Tecleado", "Apellido")


def test_nombres_desde_dni_usa_factiliza_si_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_dni",
        lambda self, dni: ConsultaPersona(True, dni, "CARLOS RENATO", "ROJAS DEL AGUILA", {}),
    )
    assert nombres_desde_dni("73632127", "Tecleado", "Apellido") == (
        "CARLOS RENATO",
        "ROJAS DEL AGUILA",
    )


def test_razon_social_desde_ruc_hace_fallback_si_no_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_ruc",
        lambda self, ruc: ConsultaEmpresa(False, ruc, "", "", "", {}),
    )
    assert razon_social_desde_ruc("20610077782", "Tecleado SAC") == "Tecleado SAC"


def test_razon_social_desde_ruc_usa_factiliza_si_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_ruc",
        lambda self, ruc: ConsultaEmpresa(True, ruc, "SERVICIOS RENTAURANT S.A.C", "", "", {}),
    )
    assert razon_social_desde_ruc("20610077782", "Tecleado SAC") == "SERVICIOS RENTAURANT S.A.C"
