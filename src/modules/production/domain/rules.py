"""Reglas de negocio de producción. Puras, sin infraestructura."""

from decimal import Decimal

RESULTADOS_NO_CONFORME = {"no_conforme_reprocesado", "no_conforme_desechado"}
RESULTADOS_CONTROL_CALIDAD = {"conforme"} | RESULTADOS_NO_CONFORME


def equipo_dentro_rango(temperatura_c: Decimal, rango_min: Decimal, rango_max: Decimal) -> bool:
    return rango_min <= temperatura_c <= rango_max


def checklist_aprobado(
    *,
    bioseguridad_ok: bool,
    superficies_ok: bool,
    limpieza_intermedia_ok: bool,
    equipos_dentro_rango: list[bool],
    plaga_indicio: bool,
) -> bool:
    """RN-CDP-002/005: un checklist se aprueba solo si los tres controles
    básicos están OK, ningún equipo de frío está fuera de rango y no hay
    indicio de plaga. Cualquier falla bloquea la cocina entera, no solo el
    equipo puntual — mismo criterio que `data-model.md` §7 y el SOP de
    inocuidad, más estricto que la letra de RN-CDP-005 (que solo habla de
    detener "ese equipo")."""
    return (
        bioseguridad_ok
        and superficies_ok
        and limpieza_intermedia_ok
        and all(equipos_dentro_rango)
        and not plaga_indicio
    )


def puede_registrar_consumo(estado: str) -> bool:
    return estado == "borrador"


def puede_completar(estado: str) -> bool:
    return estado == "en_proceso"


def puede_iniciar_plan(estado: str) -> bool:
    return estado == "planificado"


def puede_cerrar_plan(estado: str) -> bool:
    return estado == "en_ejecucion"


def puede_visar_reporte(visado_at) -> bool:
    """RN-DOC-010: se visa una sola vez — el reporte ya visado queda
    congelado, no se puede reabrir."""
    return visado_at is None


def costo_real_unitario(
    costo_insumos: Decimal, costo_mano_obra: Decimal, cantidad_producida: Decimal
) -> Decimal:
    if cantidad_producida <= 0:
        raise ValueError("cantidad_producida debe ser > 0 para costear")
    return (costo_insumos + costo_mano_obra) / cantidad_producida
