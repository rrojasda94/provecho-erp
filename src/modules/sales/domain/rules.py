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


def precio_unitario_neto(
    cantidad: Decimal, precio_unitario: Decimal, descuento: Decimal
) -> Decimal:
    """Precio por unidad ya descontado. El descuento de `venta_item` es un
    monto sobre la línea completa; el comprobante electrónico lo necesita
    repartido por unidad."""
    if cantidad <= 0:
        return precio_unitario
    return precio_unitario - (descuento / cantidad)


# --- Comprobante electrónico -------------------------------------------------
# Catálogo 06 de SUNAT (tipo de documento de identidad).
DOC_SUNAT_SIN_DOCUMENTO = "0"
DOC_SUNAT_DNI = "1"
DOC_SUNAT_CARNE_EXTRANJERIA = "4"
DOC_SUNAT_RUC = "6"
DOC_SUNAT_PASAPORTE = "7"

_DOC_SUNAT_POR_TIPO_PERSONA = {
    "dni": DOC_SUNAT_DNI,
    "ce": DOC_SUNAT_CARNE_EXTRANJERIA,
    "pasaporte": DOC_SUNAT_PASAPORTE,
}


def doc_sunat_de_persona(tipo_documento: str) -> str:
    return _DOC_SUNAT_POR_TIPO_PERSONA.get(tipo_documento, DOC_SUNAT_SIN_DOCUMENTO)


def tipo_comprobante(tipo_cliente: str | None, ruc: str | None) -> str:
    """Factura solo si el cliente es jurídico y tiene RUC; en todo otro
    caso boleta, incluido el cliente anónimo (RN-PER-005)."""
    return "factura" if tipo_cliente == "juridico" and ruc else "boleta"


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
