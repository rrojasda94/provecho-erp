# ruff: noqa: F811  (el fixture `env` se importa y se pide como argumento)
"""Recuperar, restablecer y cambiar la clave de una cuenta del sitio, y el reset
asistido por atención al cliente (RN-WEB-018/019, ADR-104)."""

import re

import pytest
from sqlalchemy import select

from src.modules.storefront.infrastructure import security
from src.modules.storefront.infrastructure.models import StorefrontCuenta
from tests.test_storefront_cuentas import CUENTAS, _registro_body, env  # noqa: F401

RECUPERAR = f"{CUENTAS}/recuperar"
RESTABLECER = f"{CUENTAS}/restablecer"
CLIENTES = "/api/v1/storefront/clientes"
CLAVE = "clave-larga-123"


@pytest.fixture()
def correos(monkeypatch):
    """Captura los correos que saldrían por SMTP."""
    from src.shared.integrations.email import smtp

    enviados: list[tuple[str, str, str]] = []
    monkeypatch.setattr(smtp, "configurado", lambda: True)
    monkeypatch.setattr(
        smtp,
        "enviar",
        lambda *, destinatario, asunto, cuerpo: enviados.append((destinatario, asunto, cuerpo)),
    )
    return enviados


def _token_del_correo(correos) -> str:
    return re.search(r"token=([\w.\-]+)", correos[-1][2]).group(1)


def _registrar(client):
    r = client.post(f"{CUENTAS}/registro", json=_registro_body())
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, clave):
    return client.post(f"{CUENTAS}/login", json={"email": "ana@example.com", "password": clave})


def _erp(client, usuario="admin"):
    r = client.post("/api/v1/auth/login", json={"username": usuario, "pin": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_recuperar_responde_igual_exista_o_no_el_correo(env, correos):
    client, _, _ = env
    _registrar(client)
    existente = client.post(RECUPERAR, json={"email": "ana@example.com"})
    ajeno = client.post(RECUPERAR, json={"email": "nadie@example.com"})
    assert existente.status_code == ajeno.status_code == 202
    assert existente.json() == ajeno.json()  # no delata qué correos tienen cuenta
    assert [c[0] for c in correos] == ["ana@example.com"]
    assert "30 minutos" in correos[0][2]


def test_el_enlace_cambia_la_clave_una_sola_vez_y_cierra_las_sesiones(env, correos):
    client, _, _ = env
    sesion_vieja = _registrar(client)
    client.post(RECUPERAR, json={"email": "ana@example.com"})
    token = _token_del_correo(correos)

    r = client.post(RESTABLECER, json={"token": token, "password": "otra-clave-456"})
    assert r.status_code == 204, r.text
    assert _login(client, "otra-clave-456").status_code == 200
    assert _login(client, CLAVE).status_code == 401
    # Un solo uso: la clave cambió, el mismo enlace ya no vale.
    again = client.post(RESTABLECER, json={"token": token, "password": "tercera-789"})
    assert again.status_code == 401
    # Quien tuviera la sesión abierta con la clave vieja queda afuera.
    viejo = client.post(f"{CUENTAS}/refresh", json={"refresh_token": sesion_vieja["refresh_token"]})
    assert viejo.status_code == 401


def test_un_enlace_vencido_o_de_otra_clase_no_sirve(env, correos, monkeypatch):
    client, _, _ = env
    sesion = _registrar(client)

    monkeypatch.setattr(security, "RESET_MINUTOS", -1)  # nace vencido
    client.post(RECUPERAR, json={"email": "ana@example.com"})
    vencido = _token_del_correo(correos)
    r = client.post(RESTABLECER, json={"token": vencido, "password": "otra-clave-456"})
    assert r.status_code == 401

    # Un token de sesión no vale como enlace...
    de_sesion = {"token": sesion["access_token"], "password": "otra-clave-456"}
    assert client.post(RESTABLECER, json=de_sesion).status_code == 401
    # ...ni el enlace como token de sesión (otra audiencia).
    monkeypatch.setattr(security, "RESET_MINUTOS", 30)
    client.post(RECUPERAR, json={"email": "ana@example.com"})
    enlace = _token_del_correo(correos)
    me = client.get(f"{CUENTAS}/me", headers={"Authorization": f"Bearer {enlace}"})
    assert me.status_code == 401


def test_una_cuenta_solo_google_puede_ponerse_clave_por_correo(env, correos):
    client, _, TestSession = env
    _registrar(client)
    with TestSession() as s:
        cuenta = s.scalar(select(StorefrontCuenta))
        cuenta.password_hash = None
        cuenta.google_sub = "google-123"
        s.commit()
    client.post(RECUPERAR, json={"email": "ana@example.com"})
    token = _token_del_correo(correos)
    r = client.post(RESTABLECER, json={"token": token, "password": "recien-puesta-1"})
    assert r.status_code == 204
    assert _login(client, "recien-puesta-1").status_code == 200


def test_sin_correo_configurado_recuperar_no_falla(env, monkeypatch):
    from src.shared.integrations.email import smtp

    monkeypatch.setattr(smtp, "configurado", lambda: False)
    client, _, _ = env
    _registrar(client)
    assert client.post(RECUPERAR, json={"email": "ana@example.com"}).status_code == 202


def test_una_clave_corta_se_rechaza(env, correos):
    client, _, _ = env
    _registrar(client)
    client.post(RECUPERAR, json={"email": "ana@example.com"})
    r = client.post(RESTABLECER, json={"token": _token_del_correo(correos), "password": "corta"})
    assert r.status_code == 422


def test_atencion_restablece_la_clave_y_obliga_a_cambiarla(env):
    client, _, _ = env
    sesion_vieja = _registrar(client)
    admin = _erp(client)

    lista = client.get(CLIENTES, headers=admin, params={"q": "ana"})
    assert lista.status_code == 200, lista.text
    assert [c["email"] for c in lista.json()] == ["ana@example.com"]
    assert "password_hash" not in lista.text  # nunca la clave, ni su hash
    cuenta_id = lista.json()[0]["id"]

    r = client.post(f"{CLIENTES}/{cuenta_id}/restablecer-clave", headers=admin)
    assert r.status_code == 200, r.text
    temporal = r.json()["clave_temporal"]
    assert len(temporal) == 8

    # La clave vieja ya no entra, la temporal sí, y las sesiones viejas se cerraron.
    assert _login(client, CLAVE).status_code == 401
    entrada = _login(client, temporal)
    assert entrada.status_code == 200
    headers = {"Authorization": f"Bearer {entrada.json()['access_token']}"}
    assert client.get(f"{CUENTAS}/me", headers=headers).json()["debe_cambiar_clave"] is True
    viejo = client.post(f"{CUENTAS}/refresh", json={"refresh_token": sesion_vieja["refresh_token"]})
    assert viejo.status_code == 401

    # Elegir una propia exige la temporal y apaga la obligación.
    mala = client.patch(
        f"{CUENTAS}/me/clave", headers=headers,
        json={"clave_actual": "no-es-esta", "clave_nueva": "mi-clave-propia-1"},
    )
    assert mala.status_code == 401
    ok = client.patch(
        f"{CUENTAS}/me/clave", headers=headers,
        json={"clave_actual": temporal, "clave_nueva": "mi-clave-propia-1"},
    )
    assert ok.status_code == 204, ok.text
    assert client.get(f"{CUENTAS}/me", headers=headers).json()["debe_cambiar_clave"] is False
    assert _login(client, "mi-clave-propia-1").status_code == 200
    assert _login(client, temporal).status_code == 401


def test_solo_quien_tiene_permiso_atiende_cuentas(env):
    client, _, _ = env
    _registrar(client)
    cajero = _erp(client, "cajero1")
    assert client.get(CLIENTES, headers=cajero).status_code == 403
    cuenta_id = _erp_lista_id(client)
    r = client.post(f"{CLIENTES}/{cuenta_id}/restablecer-clave", headers=cajero)
    assert r.status_code == 403


def _erp_lista_id(client) -> str:
    return client.get(CLIENTES, headers=_erp(client)).json()[0]["id"]


def test_restablecer_una_cuenta_que_no_existe_es_404(env):
    client, _, _ = env
    r = client.post(
        f"{CLIENTES}/00000000-0000-0000-0000-000000000000/restablecer-clave", headers=_erp(client)
    )
    assert r.status_code == 404
