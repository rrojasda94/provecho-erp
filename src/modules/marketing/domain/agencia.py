"""Puntuación y recomendación de la evaluación agencia vs. interna
(RN-MKT-006). Pura: sin ORM, sin red.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PUNTAJE_MIN = 1
PUNTAJE_MAX = 5
PESO_TOTAL = 100


@dataclass(frozen=True)
class Propuesta:
    id: str
    tipo: str  # agencia | interna
    costo: Decimal
    puntaje_total: Decimal


def criterios_validos(criterios: list[dict]) -> list[str]:
    """Problemas de la ponderación. Vacío = se puede evaluar con ella."""
    if not criterios:
        return ["hay que declarar al menos un criterio"]
    problemas = []
    codigos = [c.get("codigo") for c in criterios]
    if len(set(codigos)) != len(codigos) or not all(codigos):
        problemas.append("los criterios necesitan un código único cada uno")
    suma = sum(Decimal(str(c.get("peso", 0))) for c in criterios)
    if suma != PESO_TOTAL:
        problemas.append(f"los pesos suman {suma}; tienen que sumar {PESO_TOTAL}")
    return problemas


def puntaje_ponderado(criterios: list[dict], puntajes: dict) -> Decimal:
    """Nota de 1 a 5 ponderada por los pesos declarados.

    Un criterio sin puntuar vale 0 y no se descuenta del divisor: dejar en
    blanco lo que no conviene sería la forma más fácil de ganar la
    comparación.
    """
    total = sum(
        Decimal(str(puntajes.get(c["codigo"], 0))) * Decimal(str(c["peso"]))
        for c in criterios
    )
    return (total / PESO_TOTAL).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def puntajes_validos(criterios: list[dict], puntajes: dict) -> list[str]:
    problemas = []
    esperados = {c["codigo"] for c in criterios}
    sobran = set(puntajes) - esperados
    if sobran:
        problemas.append(f"criterios que no son de esta evaluación: {sorted(sobran)}")
    for codigo, valor in puntajes.items():
        if codigo in esperados and not _en_rango(valor):
            problemas.append(f"'{codigo}' fuera de rango ({PUNTAJE_MIN}-{PUNTAJE_MAX})")
    return problemas


def recomendada(propuestas: list[Propuesta], presupuesto: Decimal) -> Propuesta | None:
    """La mejor puntuada **entre las que caben en el presupuesto**.

    El presupuesto filtra antes de comparar y no descuenta puntos: una
    propuesta que se pasa no es "un poco peor", es una que no se puede pagar
    (RN-GER-003). Si ninguna cabe, devuelve la mejor puntuada igual — la
    decisión pasa a ser de Gerencia, y para eso necesita ver un candidato.
    """
    if not propuestas:
        return None
    dentro = [p for p in propuestas if p.costo <= presupuesto]
    return max(dentro or propuestas, key=lambda p: (p.puntaje_total, -p.costo))


def exige_motivo(elegida: Propuesta, sugerida: Propuesta | None, presupuesto: Decimal) -> bool:
    """Apartarse de la recomendación o del presupuesto se puede; en silencio
    no. Es el único control real que le queda a Gerencia sobre esta decisión.
    """
    return elegida.costo > presupuesto or (sugerida is not None and elegida.id != sugerida.id)


def comparable(tipos: list[str]) -> bool:
    """Sin la opción interna no hay comparación: elegir entre tres agencias
    no contesta si hace falta una agencia (RN-MKT-006)."""
    return "interna" in tipos and len(tipos) >= 2


def _en_rango(valor: object) -> bool:
    try:
        numero = Decimal(str(valor))
    except (ArithmeticError, ValueError, TypeError):
        return False
    return PUNTAJE_MIN <= numero <= PUNTAJE_MAX
