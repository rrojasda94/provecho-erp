"""Errores de aplicación de marketing. La tripleta común (`NoEncontrado`,
`Conflicto`, `ReglaNegocio`) y su mapeo a HTTP viven en
`src/shared/errors.py`; el módulo no especializa ninguno todavía.

Hasta 2026-08-08 marketing tenía su propia jerarquía sobre `Exception` y
cada endpoint repetía el `try/except … raise _http(e)` — el patrón que
`src/core/error_handlers.py` ya había centralizado para los otros siete
módulos. Al heredar de la base compartida, el handler global responde con
los mismos códigos y los routers dejan de traducir nada.
"""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "Conflicto", "NoEncontrado", "ReglaNegocio"]
