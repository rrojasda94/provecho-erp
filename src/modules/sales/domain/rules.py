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
