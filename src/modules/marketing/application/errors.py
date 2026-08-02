"""Errores de la capa de aplicación de marketing (la API los mapea a HTTP)."""


class MarketingError(Exception):
    """Base."""


class NoEncontrado(MarketingError):
    """Entidad inexistente."""


class Conflicto(MarketingError):
    """Estado que no admite la operación."""


class ReglaNegocio(MarketingError):
    """Violación de una regla (brief incompleto, contenido no pertinente, etc.)."""
