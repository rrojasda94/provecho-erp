"""Primitivas de seguridad: hash de PIN (Argon2id), JWT y refresh tokens.

Adaptador de infraestructura: aísla las librerías (argon2, PyJWT) del
dominio y la aplicación.
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

_hasher = PasswordHasher()


def hash_pin(pin: str) -> str:
    return _hasher.hash(pin)


def verify_pin(pin_hash: str, pin: str) -> bool:
    try:
        _hasher.verify(pin_hash, pin)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(claims: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodifica y valida firma/expiración. Lanza jwt.PyJWTError si es inválido."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def new_refresh_token() -> tuple[str, str]:
    """Devuelve (token_en_claro, token_hash). Solo el hash se persiste."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_expira_en() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
