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


def puede_aprobar(solicitante_id, aprobador_id) -> bool:
    """Segregación de funciones: el aprobador no puede ser el solicitante
    (RN-INV-015)."""
    return solicitante_id != aprobador_id


def stock_bajo(cantidad: Decimal, stock_minimo: Decimal | None) -> bool:
    return stock_minimo is not None and cantidad <= stock_minimo
