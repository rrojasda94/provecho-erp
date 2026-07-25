"""Errores de la capa de aplicación de production (la API los mapea a HTTP)."""


class ProductionError(Exception):
    """Base."""


class NoEncontrado(ProductionError):
    """Entidad inexistente."""


class Conflicto(ProductionError):
    """Estado que no admite la operación."""


class ReglaNegocio(ProductionError):
    """Violación de una regla (receta inexistente, resultado inválido, etc.)."""
