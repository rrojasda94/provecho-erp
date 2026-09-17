"""Verificación del `id_token` de "Continuar con Google" (ADR-102).

El navegador nunca es la fuente de verdad de quién inició sesión: manda el
`id_token` que Google le dio, y este módulo lo valida contra las claves
públicas de Google (JWKS) — firma, expiración, emisor y **audiencia**
(`GOOGLE_OAUTH_CLIENT_ID`, el mismo Client ID que usa el botón en el
navegador). Sin esa validación, cualquiera podría mandar un JWT inventado
con el email que quisiera.

Usa `jwt.PyJWKClient` (ya viene con PyJWT, sin dependencia nueva) en vez de
la librería oficial `google-auth`: es una verificación de firma estándar,
no hace falta el SDK completo para una sola operación.
"""

import jwt
from jwt import PyJWKClient

from src.config.settings import settings

_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_EMISORES_VALIDOS = ("accounts.google.com", "https://accounts.google.com")

# Un cliente por proceso: cachea las claves de Google (rotan poco) en vez
# de pedirlas en cada login.
_jwks_client: PyJWKClient | None = None


def _cliente() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_JWKS_URL)
    return _jwks_client


class GoogleTokenInvalido(Exception):
    """El `id_token` no es de Google, expiró, o es de otra aplicación."""


def verificar_id_token(id_token: str) -> dict:
    """`{sub, email, email_verified, nombres, apellidos}` del token
    verificado. Lanza `GoogleTokenInvalido` — nunca deja pasar un token sin
    firma válida."""
    if not settings.google_oauth_client_id:
        raise GoogleTokenInvalido("Google Sign-In no está configurado")
    try:
        clave = _cliente().get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            clave.key,
            algorithms=["RS256"],
            audience=settings.google_oauth_client_id,
        )
    except jwt.PyJWTError as e:
        raise GoogleTokenInvalido(f"id_token inválido: {e}") from e

    if payload.get("iss") not in _EMISORES_VALIDOS:
        raise GoogleTokenInvalido("emisor del token no es Google")
    if not payload.get("email"):
        raise GoogleTokenInvalido("el token de Google no trae email")

    nombre_completo = str(payload.get("name") or "").strip()
    nombres, _, apellidos = nombre_completo.partition(" ")
    return {
        "sub": payload["sub"],
        "email": payload["email"],
        "email_verified": bool(payload.get("email_verified")),
        "nombres": payload.get("given_name") or nombres or "",
        "apellidos": payload.get("family_name") or apellidos or "-",
    }
