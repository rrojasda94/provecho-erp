"""Aislamiento de credenciales entre el ERP y la cuenta del sitio de marca
(ADR-104, PR4): un token nunca sirve del otro lado, ni a nivel HTTP —varios
endpoints, no solo uno de cada— ni al decodificarlo directo, y por dos
motivos independientes (secreto distinto, `aud` exigida) que no dependen
uno del otro para sostener la garantía.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.sales.application import listeners as sales_listeners
from src.modules.sales.infrastructure.models import ProductoComercial
from src.modules.storefront.application import listeners as storefront_listeners
from src.modules.storefront.infrastructure import security as storefront_security
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure import security as users_security
from src.modules.users.infrastructure.models import Grupo, Marca

CUENTAS = "/api/v1/storefront/cuentas"


@pytest.fixture()
def env(monkeypatch, _app_compartida, _engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(sales_listeners, "session_factory", TestSession)
    monkeypatch.setattr(storefront_listeners, "session_factory", TestSession)

    from src.seeders.seed import seed

    ids = {}
    with TestSession() as s:
        seed(s)
        grupo = s.scalar(select(Grupo))
        marca = s.scalar(select(Marca).where(Marca.grupo_id == grupo.id))
        producto = ProductoComercial(id_interno="P0000077", marca_id=marca.id, nombre="Pizza")
        s.add(producto)
        s.flush()
        ids.update(marca_id=str(marca.id), producto_id=str(producto.id))
        s.commit()

    from src.config.settings import settings

    monkeypatch.setattr(settings, "storefront_marca_id", ids["marca_id"])

    app = _app_compartida

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c, ids


def _registro_body():
    return {
        "email": "aislamiento@example.com", "password": "clave-larga-123", "nombres": "Ana",
        "apellidos": "Torres", "tipo_documento": "dni", "numero_documento": "45678912",
        "telefono": "987654321", "fecha_nacimiento": "1995-05-20",
    }


def _token_cuenta(client) -> str:
    return client.post(f"{CUENTAS}/registro", json=_registro_body()).json()["access_token"]


def _token_erp(client) -> str:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "pin": "123456"})
    return r.json()["access_token"]


# --- Un token de cuenta web nunca abre ni un endpoint del ERP ni uno de -----
# gestión del propio storefront que exige JWT del ERP con permiso.
@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/sales/ventas"),
        (
            "GET",
            "/api/v1/storefront/contenido?marca_id="
            + "0" * 8 + "-0000-0000-0000-000000000000",
        ),
    ],
)
def test_token_de_cuenta_web_no_abre_endpoints_del_erp(env, metodo, ruta):
    client, _ids = env
    token = _token_cuenta(client)
    r = client.request(metodo, ruta, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, f"{metodo} {ruta} -> {r.status_code}"


# --- Un token del ERP nunca abre un endpoint de cuenta del sitio ------------
@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("GET", f"{CUENTAS}/me"),
        ("GET", f"{CUENTAS}/me/direcciones"),
        ("GET", f"{CUENTAS}/me/favoritos"),
        ("GET", f"{CUENTAS}/me/ultimo-pedido"),
    ],
)
def test_token_del_erp_no_abre_endpoints_de_cuenta_web(env, metodo, ruta):
    client, _ids = env
    token = _token_erp(client)
    r = client.request(metodo, ruta, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, f"{metodo} {ruta} -> {r.status_code}"


# --- A nivel de decode: dos razones independientes, no una sola ------------
def test_decodificar_token_del_erp_con_el_decoder_de_storefront_falla_por_firma(env):
    client, _ids = env
    token_erp = _token_erp(client)
    with pytest.raises(jwt.PyJWTError):
        storefront_security.decode_access_token(token_erp)


def test_decodificar_token_de_cuenta_con_el_decoder_del_erp_falla_por_firma(env):
    client, _ids = env
    token_cuenta = _token_cuenta(client)
    with pytest.raises(jwt.PyJWTError):
        users_security.decode_access_token(token_cuenta)


def test_un_token_firmado_con_el_secreto_correcto_pero_sin_aud_no_sirve(env, monkeypatch):
    """Aunque alguien consiguiera el secreto de storefront (fuga, backup mal
    protegido), un token que no declare `aud="storefront"` sigue sin sobrar
    en este endpoint — la firma no alcanza sola."""
    from src.config.settings import settings

    payload = {
        "sub": str(uuid.uuid4()),
        "email": "quien-sea@example.com",
        "exp": datetime.now(UTC) + timedelta(days=1),
    }
    token_sin_aud = jwt.encode(payload, settings.storefront_jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        storefront_security.decode_access_token(token_sin_aud)


def test_forjar_aud_storefront_con_el_secreto_del_erp_no_alcanza(env, monkeypatch):
    """El caso inverso: declarar `aud="storefront"` a mano no sirve si el
    token está firmado con el secreto del ERP — la firma se verifica
    primero, la `aud` nunca llega a mirarse.

    Los dos secretos comparten el mismo placeholder por defecto
    (`change-me`) hasta que alguien configura el `.env` — en desarrollo o
    en este mismo test sin fijarlos a mano serían iguales por coincidencia,
    y esta prueba dejaría de probar lo que dice probar. Se fuerzan
    distintos para aislar la garantía real: la `aud` sola no basta, hace
    falta además que el secreto sea el correcto."""
    from src.config.settings import settings

    monkeypatch.setattr(settings, "jwt_secret", "secreto-del-erp-" + "x" * 32)
    monkeypatch.setattr(settings, "storefront_jwt_secret", "secreto-de-storefront-" + "y" * 32)
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "forjado@example.com",
        "aud": "storefront",
        "exp": datetime.now(UTC) + timedelta(days=1),
    }
    token_forjado = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        storefront_security.decode_access_token(token_forjado)
