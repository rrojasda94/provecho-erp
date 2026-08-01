"""Errores propios de users. La tripleta común y su mapeo a HTTP viven en
`src/shared/errors.py`; los de autenticación son específicos del módulo y
su estado HTTP lo registra `src/modules/users/api/error_handlers.py`."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = [
    "AppError",
    "Conflicto",
    "CredencialesInvalidas",
    "NoEncontrado",
    "PinInvalido",
    "ReglaNegocio",
    "TokenInvalido",
    "UsuarioBloqueado",
]


class CredencialesInvalidas(AppError):
    """Usuario o PIN incorrectos."""


class UsuarioBloqueado(AppError):
    """Lockout por intentos fallidos."""


class TokenInvalido(AppError):
    """Refresh token inválido, expirado o reutilizado."""


class PinInvalido(AppError):
    """El PIN no cumple el formato exigido."""
