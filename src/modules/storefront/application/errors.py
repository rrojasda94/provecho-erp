"""Errores de aplicación de storefront. La tripleta común (`NoEncontrado`,
`Conflicto`, `ReglaNegocio`) y su mapeo a HTTP viven en
`src/shared/errors.py`. Los cuatro de autenticación de cuenta (ADR-102) son
propios — mismo criterio que `users.application.errors` — y su estado HTTP
lo registra `api/error_handlers.py`."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = [
    "AppError",
    "Conflicto",
    "CredencialesInvalidas",
    "CuentaBloqueada",
    "NoEncontrado",
    "ReglaNegocio",
    "TokenInvalido",
]


class CredencialesInvalidas(AppError):
    """Email o clave incorrectos, o `id_token` de Google inválido."""


class CuentaBloqueada(AppError):
    """Lockout por intentos fallidos de clave."""


class TokenInvalido(AppError):
    """Refresh token de cuenta inválido, expirado o reutilizado."""
