"""Errores de la capa de aplicación de users.

La capa API los mapea a códigos HTTP (401/403/404/409/422).
"""


class UsersError(Exception):
    """Base."""


class CredencialesInvalidas(UsersError):
    """Username o PIN incorrectos, o usuario inactivo."""


class UsuarioBloqueado(UsersError):
    """Login bloqueado por intentos fallidos."""


class TokenInvalido(UsersError):
    """Refresh token ausente, expirado o revocado."""


class NoEncontrado(UsersError):
    """Entidad inexistente."""


class Conflicto(UsersError):
    """Violación de unicidad (username/código/nombre duplicado)."""


class PinInvalido(UsersError):
    """El PIN no cumple el formato (6 dígitos)."""
