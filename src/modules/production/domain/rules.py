"""Reglas de negocio de producción. Puras, sin infraestructura."""

from decimal import Decimal

RESULTADOS_NO_CONFORME = {"no_conforme_reprocesado", "no_conforme_desechado"}
RESULTADOS_CONTROL_CALIDAD = {"conforme"} | RESULTADOS_NO_CONFORME


def puede_registrar_consumo(estado: str) -> bool:
    return estado == "borrador"


def puede_completar(estado: str) -> bool:
    return estado == "en_proceso"


def costo_real_unitario(
    costo_insumos: Decimal, costo_mano_obra: Decimal, cantidad_producida: Decimal
) -> Decimal:
    if cantidad_producida <= 0:
        raise ValueError("cantidad_producida debe ser > 0 para costear")
    return (costo_insumos + costo_mano_obra) / cantidad_producida
