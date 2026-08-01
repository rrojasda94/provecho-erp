"""Errores propios de sales. La tripleta común (`NoEncontrado`, `Conflicto`,
`ReglaNegocio`) y su mapeo a HTTP viven en `src/shared/errors.py`; acá solo
lo que sales especializa."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "Conflicto", "NoEncontrado", "PrecioNoDefinido", "ReglaNegocio"]


class PrecioNoDefinido(ReglaNegocio):
    """Ninguna `lista_precio` vigente cubre el producto en ese ámbito. La
    venta no se confirma: el precio nunca lo pone el cliente (RN-PRC-003)."""
