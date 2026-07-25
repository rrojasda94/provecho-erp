"""Errores de la capa de aplicación de inventory (la API los mapea a HTTP)."""


class InventoryError(Exception):
    """Base."""


class NoEncontrado(InventoryError):
    """Entidad inexistente."""


class Conflicto(InventoryError):
    """Violación de unicidad (id_interno / código / nombre duplicado)."""


class ReglaNegocio(InventoryError):
    """Violación de una regla (segregación, estado inválido, tipo inválido)."""


class StockInsuficiente(InventoryError):
    """Una salida dejaría el stock en negativo."""
