"""Errores de la capa de aplicación de sales (la API los mapea a HTTP)."""


class SalesError(Exception):
    """Base."""


class NoEncontrado(SalesError):
    """Entidad inexistente."""


class Conflicto(SalesError):
    """Duplicado (id_interno) o estado que no admite la operación."""


class ReglaNegocio(SalesError):
    """Violación de regla (canal/modalidad inválida, sobrepago, etc.)."""


class PrecioNoDefinido(ReglaNegocio):
    """Ninguna `lista_precio` vigente cubre el producto en ese ámbito. La
    venta no se confirma: el precio nunca lo pone el cliente (RN-PRC-003)."""
