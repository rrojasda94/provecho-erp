"""Errores propios de inventory. La tripleta común y su mapeo a HTTP viven
en `src/shared/errors.py`."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "Conflicto", "NoEncontrado", "ReglaNegocio", "StockInsuficiente"]


class StockInsuficiente(ReglaNegocio):
    """Una salida dejaría el stock en negativo."""
