"""Errores de la capa de aplicación de accounting (la API los mapea a HTTP)."""


class AccountingError(Exception):
    """Base."""


class NoEncontrado(AccountingError):
    """Entidad inexistente."""


class Conflicto(AccountingError):
    """Estado que no admite la operación."""


class ReglaNegocio(AccountingError):
    """Violación de una regla (descuadre, periodo cerrado, cuenta inactiva)."""
