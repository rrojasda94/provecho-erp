"""Errores de aplicación de production. La tripleta común (`NoEncontrado`,
`Conflicto`, `ReglaNegocio`) y su mapeo a HTTP viven en
`src/shared/errors.py`."""

from src.shared.errors import AppError, Conflicto, NoEncontrado, ReglaNegocio

__all__ = ["AppError", "CocinaBloqueada", "Conflicto", "NoEncontrado", "ReglaNegocio"]


class CocinaBloqueada(Conflicto):
    """No hay checklist de inocuidad aprobado del turno vigente en el
    almacén (RN-CDP-005): `crear_orden_produccion` y `registrar_consumo`
    rechazan mientras la cocina siga así."""
