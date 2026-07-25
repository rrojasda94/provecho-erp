"""Reglas de dominio del libro contable: tipos de cuenta, cuadre de asiento
y qué admite un periodo según su estado (RN-CTB-001/002)."""

from decimal import Decimal

TIPOS_CUENTA = ("activo", "pasivo", "patrimonio", "ingreso", "gasto")
_NATURALEZA_DEUDORA = {"activo", "gasto"}


def naturaleza_de_tipo(tipo: str) -> str:
    return "deudora" if tipo in _NATURALEZA_DEUDORA else "acreedora"


def cuadra(total_debe: Decimal, total_haber: Decimal) -> bool:
    return total_debe == total_haber


def puede_registrar(periodo_estado: str) -> bool:
    return periodo_estado == "abierto"


def puede_cerrar(periodo_estado: str) -> bool:
    return periodo_estado == "abierto"
