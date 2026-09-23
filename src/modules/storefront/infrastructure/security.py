"""Primitivas de seguridad de la cuenta del sitio (ADR-104).

Deliberadamente **no** importa `src.modules.users.infrastructure.security`:
aunque el código sería casi idéntico, importar de `users` acoplaría el
aislamiento de credenciales a un módulo que no tiene por qué saber que
existe una cuenta de cliente web, y la duplicación es la mitad de un
archivo pequeño. Lo que sí comparten a propósito son las librerías
(argon2, PyJWT) y el algoritmo — no el secreto, no la `aud`, no la tabla.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src.config.settings import settings

#: Toda cuenta web es de este público — es lo que un endpoint del ERP
#: rechazaría si alguien intentara colarlo ahí, y lo que este módulo exige
#: al decodificar (nunca acepta un token sin esta `aud`, ni uno del ERP que
#: por casualidad tuviera el mismo secreto).
AUDIENCIA = "storefront"

#: El enlace de recuperar clave no es una sesión: otra audiencia, para que ni
#: un token de acceso valga como enlace ni el enlace como token de acceso.
AUDIENCIA_RESET = "storefront-reset"
RESET_MINUTOS = 30

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(claims: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims,
        "aud": AUDIENCIA,
        "iat": now,
        "exp": now + timedelta(minutes=settings.storefront_access_token_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.storefront_jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodifica y valida firma/expiración/`aud`. Lanza `jwt.PyJWTError`
    (incluido `InvalidAudienceError`) si es inválido — un token del ERP,
    firmado con otro secreto, ya falla en la firma antes de llegar a mirar
    la audiencia; uno que por algún motivo compartiera secreto todavía
    fallaría acá por no traer `aud="storefront"`."""
    return jwt.decode(
        token,
        settings.storefront_jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=AUDIENCIA,
    )


def huella_de_clave(password_hash: str | None) -> str:
    """Resumen corto de la clave vigente. Va dentro del enlace de recuperación:
    al cambiarse la clave la huella cambia y el enlace deja de valer (un solo
    uso, sin guardar nada). Es un hash del hash: no revela la clave."""
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def create_reset_token(cuenta_id: uuid.UUID, password_hash: str | None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(cuenta_id),
        "ph": huella_de_clave(password_hash),
        "aud": AUDIENCIA_RESET,
        "iat": now,
        "exp": now + timedelta(minutes=RESET_MINUTOS),
    }
    return jwt.encode(payload, settings.storefront_jwt_secret, algorithm=settings.jwt_algorithm)


def decode_reset_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.storefront_jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=AUDIENCIA_RESET,
    )


def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_expira_en() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.storefront_refresh_token_days)
