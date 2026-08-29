"""OAuth2 Authorization Code para el SSO del BI (Superset, ADR-082 Fase B).

Provecho es el único proveedor y hay un solo cliente confidencial
(Superset). Sin tabla nueva: el código de autorización y el access token
viven en Redis, con TTL corto — ninguno de los dos se pensó para durar una
sesión, solo el tiempo que tarda el navegador en rebotar de vuelta a
Superset y Superset en llamar a `/userinfo` una vez.

Falla **cerrado**: un Redis caído no deja pasar un login sin código. Es lo
opuesto de `core/rate_limit.py`, que falla abierto — ahí lo peor que puede
pasar es no frenar a alguien; acá lo peor sería dejar pasar a cualquiera.
"""

import secrets
import uuid

import redis

from src.config.settings import settings

_TIMEOUT_SEGUNDOS = 2

_client = redis.from_url(
    settings.redis_url,
    socket_timeout=_TIMEOUT_SEGUNDOS,
    socket_connect_timeout=_TIMEOUT_SEGUNDOS,
)

_PREFIJO_CODIGO = "oauth:bi:codigo:"
_PREFIJO_TOKEN = "oauth:bi:token:"


class OAuthError(Exception):
    """Error de protocolo (RFC 6749 §4.1.2.1/§5.2). `codigo` es el `error`
    que espera el cliente OAuth; `descripcion` es para el log y el 400."""

    def __init__(self, codigo: str, descripcion: str):
        self.codigo = codigo
        self.descripcion = descripcion
        super().__init__(descripcion)


def _cliente_valido(client_id: str, client_secret: str | None = None) -> bool:
    """Comparación de tiempo constante: un `client_secret` es un secreto
    real y no se compara con `==`, que corta apenas difiere el primer
    carácter y filtra por temporización cuánto acertó un atacante."""
    if not settings.oauth_bi_client_id or not settings.oauth_bi_client_secret:
        return False
    if not secrets.compare_digest(client_id, settings.oauth_bi_client_id):
        return False
    if client_secret is not None and not secrets.compare_digest(
        client_secret, settings.oauth_bi_client_secret
    ):
        return False
    return True


def _redirect_uri_valido(redirect_uri: str) -> bool:
    """Igualdad exacta contra lo configurado, nunca por prefijo — es la
    única defensa contra reenviar el código a un destino que no sea
    Superset."""
    return bool(settings.oauth_bi_redirect_uri) and secrets.compare_digest(
        redirect_uri, settings.oauth_bi_redirect_uri
    )


def emitir_codigo(usuario_id: uuid.UUID, client_id: str, redirect_uri: str) -> str:
    """Código de un solo uso para el usuario ya autenticado en Provecho.

    Lo llama `frontend/app/oauth/authorize/route.ts` una vez que confirmó la
    sesión (cookie httpOnly) y el permiso `bi.acceder` — nunca el navegador
    directo, y nunca sin pasar antes por ese chequeo.
    """
    if not _cliente_valido(client_id):
        raise OAuthError("unauthorized_client", "client_id desconocido")
    if not _redirect_uri_valido(redirect_uri):
        raise OAuthError("invalid_request", "redirect_uri no coincide")

    codigo = secrets.token_urlsafe(32)
    try:
        _client.setex(
            f"{_PREFIJO_CODIGO}{codigo}",
            settings.oauth_bi_codigo_ttl_segundos,
            str(usuario_id),
        )
    except redis.RedisError as e:
        raise OAuthError("server_error", "Redis no disponible") from e
    return codigo


def canjear_codigo(
    *,
    grant_type: str,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> tuple[str, int]:
    """Código → access token. `GETDEL` (Redis ≥ 6.2) hace la lectura y el
    borrado un solo comando atómico: dos canjes concurrentes con el mismo
    código nunca pueden ganar los dos — el segundo encuentra la clave ya
    borrada y falla, que es exactamente "un solo uso"."""
    if grant_type != "authorization_code":
        raise OAuthError("unsupported_grant_type", "grant_type no soportado")
    if not _cliente_valido(client_id, client_secret):
        raise OAuthError("invalid_client", "client_id/client_secret inválidos")
    if not _redirect_uri_valido(redirect_uri):
        raise OAuthError("invalid_grant", "redirect_uri no coincide")

    try:
        usuario_id_bytes = _client.getdel(f"{_PREFIJO_CODIGO}{code}")
    except redis.RedisError as e:
        raise OAuthError("server_error", "Redis no disponible") from e
    if usuario_id_bytes is None:
        raise OAuthError("invalid_grant", "código inválido, usado o vencido")

    token = secrets.token_urlsafe(32)
    ttl = settings.oauth_bi_token_ttl_segundos
    try:
        _client.setex(f"{_PREFIJO_TOKEN}{token}", ttl, usuario_id_bytes)
    except redis.RedisError as e:
        raise OAuthError("server_error", "Redis no disponible") from e
    return token, ttl


def usuario_id_del_token(access_token: str) -> uuid.UUID | None:
    """`None` tanto si el token nunca existió como si venció — misma
    respuesta (401) para las dos, no hay nada que distinguir del lado del
    cliente."""
    try:
        usuario_id_bytes = _client.get(f"{_PREFIJO_TOKEN}{access_token}")
    except redis.RedisError:
        return None
    if usuario_id_bytes is None:
        return None
    return uuid.UUID(usuario_id_bytes.decode())
