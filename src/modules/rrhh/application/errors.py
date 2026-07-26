"""Errores de la capa de aplicación de rrhh (la API los mapea a HTTP)."""


class RrhhError(Exception):
    """Base."""


class NoEncontrado(RrhhError):
    """Entidad inexistente."""


class Conflicto(RrhhError):
    """Estado que no admite la operación."""


class ReglaNegocio(RrhhError):
    """Violación de una regla de negocio."""
