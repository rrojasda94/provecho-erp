"""Reglas de negocio de compras. Puras, sin infraestructura."""

from decimal import Decimal

TIPOS_OC = {"insumo", "activo"}
CLASIFICACIONES_PROVEEDOR = {"regular", "preferente"}
CONDICIONES_PAGO = {"contado", "credito"}


def puede_emitir(estado: str) -> bool:
    return estado == "borrador"


def puede_recibir(estado: str) -> bool:
    return estado in ("emitida", "recibida_parcial")


def puede_dar_conformidad(estado: str) -> bool:
    return estado in ("recibida", "recibida_parcial")


def puede_anular(estado: str) -> bool:
    """Anulación solo antes de cualquier recepción; después, corrección vía
    nota de crédito/nueva versión (RN-CMP — OC emitida es inmutable)."""
    return estado in ("borrador", "emitida")


def requiere_aprobacion(total: Decimal, umbral: Decimal) -> bool:
    return total > umbral


def estado_tras_recepcion(items_ordenados: list[Decimal], items_recibidos: list[Decimal]) -> str:
    """Compara cantidad ordenada vs. recibida acumulada por ítem."""
    pares = zip(items_ordenados, items_recibidos, strict=True)
    if all(recibida >= ordenada for ordenada, recibida in pares):
        return "recibida"
    return "recibida_parcial"
