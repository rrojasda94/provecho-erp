"""Reglas de negocio de inventario. Puras, sin infraestructura."""

from decimal import Decimal

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
