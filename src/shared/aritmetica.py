"""Aritmética tecleada en un campo de cantidad: "1000/3", "250*1.5", "80+20".

Escalar una receta a mano obliga a sacar la calculadora por cada línea, y
ahí es donde entra el error de tipeo que después aparece como faltante de
inventario. Se acepta la operación en el propio campo y se guarda **el
resultado**, redondeado a los decimales de la unidad de medida del insumo
(RN-GER-010): el número que se ve es el que se descuenta y el que costea.

La expresión original se conserva aparte (`receta_item.expresion`) para
poder reeditarla; no se recalcula sola en ningún momento.

`ast` de la stdlib con lista blanca de nodos, nunca `eval`: el texto entra
desde la API y evaluarlo sin restricción sería ejecución remota de código.
"""

import ast
import operator
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation

from src.shared.errors import ReglaNegocio

# Suficiente para cualquier conversión de receta real y corto para que no
# haya expresión anidada que valga la pena analizar.
LARGO_MAXIMO = 60

_BINARIOS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARIOS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class ExpresionInvalida(ReglaNegocio):
    """Lo tecleado no es una operación aritmética evaluable."""


def evaluar(expresion: str) -> Decimal:
    """Resuelve `expresion` en `Decimal`. Un número suelto también es válido."""
    texto = expresion.strip()
    if not texto:
        raise ExpresionInvalida("expresión vacía")
    if len(texto) > LARGO_MAXIMO:
        raise ExpresionInvalida(
            f"expresión demasiado larga (máximo {LARGO_MAXIMO} caracteres)"
        )
    try:
        arbol = ast.parse(texto, mode="eval")
    except SyntaxError as e:
        raise ExpresionInvalida(f"expresión inválida: {texto}") from e
    return _nodo(arbol.body, texto)


def _nodo(nodo: ast.AST, texto: str) -> Decimal:
    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, bool) or not isinstance(nodo.value, (int, float)):
            raise ExpresionInvalida(f"expresión inválida: {texto}")
        try:
            return Decimal(str(nodo.value))
        except InvalidOperation as e:
            raise ExpresionInvalida(f"expresión inválida: {texto}") from e
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _UNARIOS:
        return _UNARIOS[type(nodo.op)](_nodo(nodo.operand, texto))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _BINARIOS:
        izq, der = _nodo(nodo.left, texto), _nodo(nodo.right, texto)
        try:
            return _BINARIOS[type(nodo.op)](izq, der)
        except (DivisionByZero, InvalidOperation) as e:
            raise ExpresionInvalida("división entre cero") from e
    raise ExpresionInvalida(
        f"solo se admiten + - * / y paréntesis sobre números: {texto}"
    )


def redondear(valor: Decimal, decimales: int) -> Decimal:
    """Redondea a los decimales que admite la unidad. HALF_UP, igual que en
    `shared/magnitudes.py`: el medio gramo sube, no se va al par más cercano."""
    if decimales < 0:
        raise ExpresionInvalida("los decimales de una unidad no pueden ser negativos")
    return valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def resolver(expresion: str, decimales: int) -> Decimal:
    """Evalúa y redondea en un paso: lo que hace todo campo de cantidad."""
    return redondear(evaluar(expresion), decimales)
