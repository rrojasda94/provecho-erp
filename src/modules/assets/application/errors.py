"""Errores de aplicación de assets. La tripleta común
(`NoEncontrado`/`Conflicto`/`ReglaNegocio`) vive en `src/shared/errors.py`."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "Conflicto", "NoEncontrado", "ReglaNegocio"]
