"""Cliente HTTP de Superset (ADR-081 Fase D): solo pide *guest tokens* para
embeber tableros en `/dashboard`. Único punto del ERP que habla con la API
de administración de Superset — el dominio nunca la llama.

No es lo mismo que `src/core/oauth/` (Fase B): aquello es Provecho actuando
de PROVEEDOR OAuth2 para que un humano entre a Superset por SSO. Esto es
Provecho actuando de CLIENTE de la API de Superset, con una cuenta de
servicio propia, para conseguir un token de sesión acotado a un dashboard
puntual — dos direcciones de la misma integración, sin nada en común salvo
el destino.
"""

import httpx

from src.config.settings import settings


class SupersetError(RuntimeError):
    """Fallo de transporte, autenticación o respuesta ilegible. La cuenta de
    servicio no está configurada, Superset no responde, o el dashboard no
    existe — el llamador decide si eso apaga el embebido o revienta."""


def _sesion() -> httpx.Client:
    if not (
        settings.superset_internal_url
        and settings.superset_service_username
        and settings.superset_service_password
    ):
        raise SupersetError("Superset no está configurado (SUPERSET_* vacío)")

    c = httpx.Client(base_url=settings.superset_internal_url.rstrip("/"), timeout=10)
    try:
        r = c.post(
            "/api/v1/security/login",
            json={
                "username": settings.superset_service_username,
                "password": settings.superset_service_password,
                "provider": "db",
                # Sin refresh: cada guest token pide su propia sesión de
                # servicio. Nadie guarda este access token entre requests.
                "refresh": False,
            },
        )
        r.raise_for_status()
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        csrf = c.get("/api/v1/security/csrf_token/")
        csrf.raise_for_status()
        c.headers["X-CSRFToken"] = csrf.json()["result"]
    except httpx.HTTPError as e:
        c.close()
        raise SupersetError(f"No se pudo autenticar contra Superset: {e}") from e
    return c


def guest_token(
    dashboard_id: str, *, username: str, first_name: str, last_name: str
) -> str:
    """Token de sesión de Superset acotado a un solo dashboard, para
    embeber sin que el usuario haga un segundo login.

    `rls` va vacío a propósito: la fila ya se filtra en el dataset (RLS de
    Fase C, contra `bi_alcance_usuario`). Un `rls` acá sería una segunda
    definición de "qué ve cada quien" que mantener sincronizada con la
    primera — exactamente el problema que ADR-081 ya acepta una vez con
    `Tenant` y no necesita aceptar dos veces.
    """
    with _sesion() as c:
        try:
            r = c.post(
                "/api/v1/security/guest_token/",
                json={
                    "resources": [{"type": "dashboard", "id": dashboard_id}],
                    "rls": [],
                    "user": {
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                    },
                },
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise SupersetError(f"No se pudo emitir el guest token: {e}") from e
        return r.json()["token"]
