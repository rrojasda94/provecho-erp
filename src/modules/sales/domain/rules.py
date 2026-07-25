"""Reglas de negocio de venta y cobro. Puras, sin infraestructura."""

from decimal import Decimal

CANALES = {"pdv", "agente_ia", "delivery"}
MODALIDADES = {"mesa", "takeout", "delivery"}


def total_venta(items: list[tuple[Decimal, Decimal, Decimal]]) -> Decimal:
    """items = [(cantidad, precio_unitario, descuento)]."""
    return sum(
        (cant * precio - desc for cant, precio, desc in items), Decimal(0)
    )


def pagos_cubren_total(pagos_confirmados: list[Decimal], total: Decimal) -> bool:
    """La venta pasa a `pagada` cuando los pagos confirmados igualan el
    total (RN-COM-016). No se admite sobrepago."""
    return sum(pagos_confirmados, Decimal(0)) == total


def puede_anular(estado: str) -> bool:
    """Solo una orden aún no pagada se anula por esta vía; anulación
    post-pago = nota de crédito (slice posterior)."""
    return estado == "orden"


# --- KDS: avance de preparación por ítem -------------------------------------
# Secuencia estricta, sin retroceso: el avance mostrado en todas las
# pantallas es la verdad única del ítem.
ORDEN_PREPARACION = ["pendiente", "en_preparacion", "listo", "entregado"]


def transicion_preparacion_valida(actual: str, nuevo: str) -> bool:
    """Solo se avanza al estado inmediatamente siguiente."""
    return (
        nuevo in ORDEN_PREPARACION
        and ORDEN_PREPARACION.index(nuevo) == ORDEN_PREPARACION.index(actual) + 1
    )


def estado_pedido(estados_items: list[str]) -> str:
    """Estado agregado del pedido para la pantalla de despacho:
    `listo` cuando TODOS los ítems están al menos listos; `entregado`
    cuando todos entregados; si no, el estado del ítem más atrasado."""
    if not estados_items:
        return "pendiente"
    return min(estados_items, key=ORDEN_PREPARACION.index)
