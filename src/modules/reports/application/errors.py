"""Errores del módulo. La jerarquía vive en `src/shared/errors.py` y el mapeo
a HTTP, una sola vez, en `src/core/error_handlers.py`."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "Conflicto", "NoEncontrado", "ReglaNegocio"]
