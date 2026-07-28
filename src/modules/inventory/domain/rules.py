"""Reglas de negocio de inventario. Puras, sin infraestructura."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

TIPOS_MOVIMIENTO = {
    "recepcion_compra",
    "transferencia_salida",
    "transferencia_entrada",
    "consumo_venta",
    "consumo_produccion",
    "produccion_entrada",
    "ajuste",
    "devolucion",
}

MOTIVOS_AJUSTE = {"sobrante", "faltante", "merma", "error_registro"}

# Dirección esperada del signo de la cantidad según el tipo de movimiento.
TIPOS_INGRESO = {"recepcion_compra", "transferencia_entrada", "produccion_entrada"}
TIPOS_SALIDA = {"transferencia_salida", "consumo_venta", "consumo_produccion"}
# `ajuste` y `devolucion` admiten signo variable (lo fija el motivo/flujo).


def signo_movimiento_valido(tipo: str, cantidad: Decimal) -> bool:
    """Ingreso exige cantidad > 0; salida exige cantidad < 0. Nunca 0."""
    if cantidad == 0:
        return False
    if tipo in TIPOS_INGRESO:
        return cantidad > 0
    if tipo in TIPOS_SALIDA:
        return cantidad < 0
    return True  # ajuste/devolucion: signo libre


def signo_ajuste_valido(motivo: str, cantidad: Decimal) -> bool:
    """sobrante > 0; faltante/merma < 0; error_registro puede ser cualquiera
    (corrección). Nunca 0."""
    if cantidad == 0:
        return False
    if motivo == "sobrante":
        return cantidad > 0
    if motivo in ("faltante", "merma"):
        return cantidad < 0
    return True


def puede_aprobar(solicitante_id, aprobador_id) -> bool:
    """Segregación de funciones: el aprobador no puede ser el solicitante
    (RN-INV-015)."""
    return solicitante_id != aprobador_id


def stock_bajo(cantidad: Decimal, stock_minimo: Decimal | None) -> bool:
    return stock_minimo is not None and cantidad <= stock_minimo


def lote_vencido(fecha_vencimiento: date | None, hoy: date) -> bool:
    """Un lote sin fecha de vencimiento nunca vence (RN-VNC-001/002)."""
    return fecha_vencimiento is not None and fecha_vencimiento < hoy


def por_vencer(fecha_vencimiento: date | None, hoy: date, dias: int) -> bool:
    """Dentro de la ventana de alerta (incluye los ya vencidos)."""
    if fecha_vencimiento is None:
        return False
    return (fecha_vencimiento - hoy).days <= dias


def repartir_fefo(
    disponibles: Sequence[tuple[Any, Decimal]], requerido: Decimal
) -> tuple[list[tuple[Any, Decimal]], Decimal]:
    """Reparte `requerido` (positivo) entre lotes YA ordenados por FEFO.

    Devuelve las asignaciones `(clave, cantidad)` y el faltante que ningún
    lote pudo cubrir — el llamador decide qué hacer con él (la venta ya
    ocurrió: se descuenta igual sin lote; un ajuste sí puede rechazarse).
    """
    asignaciones: list[tuple[Any, Decimal]] = []
    pendiente = requerido
    for clave, cantidad in disponibles:
        if pendiente <= 0:
            break
        toma = min(cantidad, pendiente)
        if toma > 0:
            asignaciones.append((clave, toma))
            pendiente -= toma
    return asignaciones, pendiente


def codigo_lote_auto(fecha: date) -> str:
    """Código por defecto cuando el origen no trae uno (RN-LOT-001).

    Dos recepciones del mismo artículo con el mismo vencimiento comparten
    lote — es lo que hace el almacén en la práctica.
    """
    return f"L{fecha:%y%m%d}"
