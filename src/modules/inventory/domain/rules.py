"""Reglas de negocio de inventario. Puras, sin infraestructura."""

from collections.abc import Sequence
from datetime import date, timedelta
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

TIPOS_CONTEO = {"rutina", "ajuste", "auditoria"}

TIPOS_RESERVA = {"solicitud", "produccion", "merma", "carrito"}
MOTIVOS_RESERVA_MERMA = {"devolucion", "rechazo_sucursal", "auditoria"}

# Estados desde los que todavía se puede cancelar una solicitud y soltar
# sus reservas (RN-INV-010). Despachada ya movió stock: eso se corrige
# recibiendo o con una transferencia de vuelta, no cancelando.
ESTADOS_SOLICITUD_CANCELABLES = {"pendiente", "aprobada"}

# Cada cuánto toca contar una categoría, en días (RN-INV-007). El período
# es en días y no en meses de calendario a propósito: el almacén cuenta
# "cada 15 días" / "cada mes", no "el mismo día de cada mes", y así el
# programa no depende de qué día tenga febrero.
# ponytail: si el negocio pide anclar al día del mes, esto pasa a
# `dateutil.relativedelta` — el resto del cálculo no cambia.
FRECUENCIAS_CONTEO: dict[str, int] = {
    "diario": 1,
    "semanal": 7,
    "quincenal": 15,
    "mensual": 30,
    "semestral": 182,
    "anual": 365,
}

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


def disponible(fisico: Decimal, reservado: Decimal) -> Decimal:
    """Stock que se puede comprometer: el físico menos lo ya prometido
    (RN-INV-009). Puede dar negativo si se reservó y después se consumió
    por otra vía —una venta nunca se bloquea por una reserva—, y eso es
    información, no un error: significa que hay una promesa sin respaldo.
    """
    return fisico - reservado


def puede_despachar(aprobada: Decimal | None, a_despachar: Decimal) -> bool:
    """Nunca más de lo aprobado (RN-INV-001). Menos sí: si el central no
    tiene todo, despacha lo que hay y la diferencia queda a la vista."""
    if aprobada is None:
        return False
    return 0 < a_despachar <= aprobada


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


def proxima_fecha_conteo(ultima: date, frecuencia: str) -> date:
    """Cuándo vuelve a tocar contar, a partir del último conteo cerrado."""
    return ultima + timedelta(days=FRECUENCIAS_CONTEO[frecuencia])


def estado_programa_conteo(proxima: date, hoy: date) -> tuple[str, int]:
    """Estado del conteo programado y días de atraso.

    Atraso 0 es el día en que vence: todavía se puede contar, no es una
    falta. Recién al día siguiente el conteo está vencido y se reporta
    (RN-INV-021).
    """
    atraso = (hoy - proxima).days
    if atraso > 0:
        return "vencido", atraso
    if atraso == 0:
        return "vence_hoy", 0
    return "al_dia", atraso


def diferencia_dentro_margen(
    cantidad_sistema: Decimal,
    diferencia: Decimal,
    margen_pct: Decimal,
    valor_diferencia: Decimal | None = None,
    piso: Decimal | None = None,
) -> bool:
    """Margen de error tolerado al ajustar por conteo (RN-INV-015).

    Dos tolerancias que conviven: el **porcentaje** sobre la cantidad y
    un **piso absoluto en dinero**. Basta cumplir una. El porcentaje solo
    castiga a las categorías baratas —2 % de S/ 30 en servilletas son 60
    céntimos, así que cualquier diferencia real escala— y una alerta que
    siempre suena es una alerta que nadie mira.

    Con stock de sistema en 0 no hay base contra la cual medir un
    porcentaje, pero el piso sí aplica: un sobrante de S/ 5 sobre stock 0 es
    ruido igual.
    """
    if diferencia == 0:
        return True
    if piso is not None and valor_diferencia is not None:
        if abs(valor_diferencia) <= abs(piso):
            return True
    if cantidad_sistema == 0:
        return False
    return abs(diferencia) <= abs(cantidad_sistema) * margen_pct / Decimal(100)


def motivo_por_diferencia(diferencia: Decimal) -> str:
    """Un conteo solo produce sobrante o faltante; merma y error de
    registro los declara una persona, no la diferencia (RN-INV-016)."""
    return "sobrante" if diferencia > 0 else "faltante"


def codigo_lote_auto(fecha: date) -> str:
    """Código por defecto cuando el origen no trae uno (RN-LOT-001).

    Dos recepciones del mismo artículo con el mismo vencimiento comparten
    lote — es lo que hace el almacén en la práctica.
    """
    return f"L{fecha:%y%m%d}"
