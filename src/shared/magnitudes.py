"""Forma del valor de una magnitud: nunca un número suelto.

Un monto sin divisa y una cantidad sin unidad de medida son datos ambiguos
—¿2000 soles o 2000 dólares? ¿5 kilos o 5 unidades?— y en un parámetro que
Gerencia aprueba esa ambigüedad se vuelve una decisión mal tomada. Toda
magnitud viaja con su unidad, y los decimales con los que se redondea salen
de esa unidad (`divisa.decimales`, `unidad_medida.decimales`), no de una
constante en el código (RN-GER-010).

Los valores adimensionales (un porcentaje, un plazo en días, una frecuencia)
no llevan unidad y pasan tal cual.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from src.shared.errors import ReglaNegocio

# Claves cuyo valor es dinero, y por lo tanto exigen `divisa`.
CLAVES_MONETARIAS = ("monto", "minimo", "maximo")
# Clave cuyo valor es una magnitud física, y por lo tanto exige `unidad_medida_id`.
CLAVE_CANTIDAD = "cantidad"


class MagnitudInvalida(ReglaNegocio):
    """El valor no declara la unidad que su magnitud exige, o al revés.

    `ReglaNegocio` y no `ValueError`: es RN-GER-010, y así el handler global
    de `core/error_handlers.py` la traduce sin que cada endpoint repita un
    `try/except`."""


@dataclass(frozen=True)
class Unidad:
    """Metadatos de la unidad, ya resueltos por quien la tiene a mano —
    `shared` no consulta el catálogo de otro módulo."""

    decimales: int
    etiqueta: str  # "S/" para una divisa, "Kilo" para una unidad de medida
    prefija: bool  # S/ 2000.00 (prefijo) vs. 5.000 Kilo (sufijo)


def unidad_requerida(valor: dict[str, Any]) -> str | None:
    """Qué clave de unidad exige este valor: `divisa`, `unidad_medida_id`, o
    `None` si es adimensional. Lanza si declara una unidad sin magnitud o
    mezcla dinero con magnitud física."""
    monetarias = [c for c in CLAVES_MONETARIAS if c in valor]
    fisica = CLAVE_CANTIDAD in valor
    if monetarias and fisica:
        raise MagnitudInvalida(
            "un valor no puede ser dinero y magnitud física a la vez: "
            f"{sorted([*monetarias, CLAVE_CANTIDAD])}"
        )
    if monetarias:
        if not valor.get("divisa"):
            raise MagnitudInvalida(
                f"{monetarias[0]} es un monto: falta 'divisa' (ej. \"PEN\")"
            )
        return "divisa"
    if fisica:
        if not valor.get("unidad_medida_id"):
            raise MagnitudInvalida(
                "cantidad es una magnitud física: falta 'unidad_medida_id'"
            )
        return "unidad_medida_id"
    if valor.get("divisa"):
        raise MagnitudInvalida(
            "declara 'divisa' pero ninguna clave monetaria "
            f"({', '.join(CLAVES_MONETARIAS)})"
        )
    if valor.get("unidad_medida_id"):
        raise MagnitudInvalida("declara 'unidad_medida_id' pero ninguna 'cantidad'")
    return None


def canonizar(valor: dict[str, Any], unidad: Unidad | None) -> tuple[dict[str, Any], str | None]:
    """Redondea las magnitudes a los decimales de su unidad y devuelve
    `(valor canónico, etiqueta legible)`. La etiqueta es lo que Gerencia lee
    al decidir: "S/ 2000.00", no "2000".

    `unidad` es `None` solo para valores adimensionales, que vuelven intactos
    y sin etiqueta."""
    if unidad is None:
        return valor, None

    claves = [c for c in CLAVES_MONETARIAS if c in valor] or [CLAVE_CANTIDAD]
    canonico = dict(valor)
    for clave in claves:
        canonico[clave] = _redondear(valor[clave], unidad.decimales, clave)
    partes = [_formatear(canonico[c], unidad) for c in claves]
    return canonico, " – ".join(partes)


def _redondear(bruto: Any, decimales: int, clave: str) -> str:
    if isinstance(bruto, bool) or not isinstance(bruto, (int, float, str, Decimal)):
        raise MagnitudInvalida(f"'{clave}' no es un número: {bruto!r}")
    try:
        numero = Decimal(str(bruto))
    except InvalidOperation as e:
        raise MagnitudInvalida(f"'{clave}' no es un número: {bruto!r}") from e
    # HALF_UP, no el HALF_EVEN por defecto de Decimal: en dinero el medio
    # centavo sube (criterio de SUNAT y del sentido común de caja).
    # Texto, no float: un monto que pasa por float pierde centavos.
    return str(numero.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP))


def _formatear(numero: str, unidad: Unidad) -> str:
    return f"{unidad.etiqueta} {numero}" if unidad.prefija else f"{numero} {unidad.etiqueta}"
