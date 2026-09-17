"""Errores de aplicación de supervision. La tripleta común vive en
`src/shared/errors.py`; el módulo no especializa ninguno todavía."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "Conflicto", "NoEncontrado", "ReglaNegocio"]
