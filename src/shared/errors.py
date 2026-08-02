"""Errores esperados de la capa de aplicación, comunes a todos los módulos.

Los siete módulos declaraban su propia tripleta `NoEncontrado`/`Conflicto`/
`ReglaNegocio` sobre una base propia, y cada router repetía el mapeo a HTTP.
Ocho copias del mismo diccionario: cuando se corrigió una (resolver por
`isinstance`, para que una subclase herede el estado de su base en vez de
caer al 400 genérico) las otras seis se quedaron con el error.

Acá vive la jerarquía; el mapeo a HTTP vive una sola vez en
`src/core/error_handlers.py`. Un módulo especializa cuando le aporta
—`StockInsuficiente(ReglaNegocio)`, `PrecioNoDefinido(ReglaNegocio)`— y no
tiene que tocar el mapeo: hereda el de su base.

Sin dependencia de FastAPI ni de HTTP: `shared` no sabe que existe una API.
"""


class AppError(Exception):
    """Error de negocio esperado. Lo que no herede de acá es un bug (→ 500)."""


class NoEncontrado(AppError):
    """La entidad pedida no existe."""


class Conflicto(AppError):
    """Duplicado, o estado que no admite la operación."""


class ReglaNegocio(AppError):
    """Violación de una regla de negocio."""
