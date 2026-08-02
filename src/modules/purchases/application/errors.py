"""Errores de aplicación de purchases. La tripleta común (`NoEncontrado`,
`Conflicto`, `ReglaNegocio`) y su mapeo a HTTP viven en
`src/shared/errors.py`; el módulo no especializa ninguno todavía."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "Conflicto", "NoEncontrado", "ReglaNegocio"]
