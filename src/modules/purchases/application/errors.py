"""Errores de la capa de aplicación de purchases (la API los mapea a HTTP)."""


class PurchasesError(Exception):
    """Base."""


class NoEncontrado(PurchasesError):
    """Entidad inexistente."""


class Conflicto(PurchasesError):
    """Estado que no admite la operación."""


class ReglaNegocio(PurchasesError):
    """Violación de una regla (tipo/condición inválida, umbral, exceso de recepción)."""
