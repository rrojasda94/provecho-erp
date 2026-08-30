"""Reglas de negocio de inventario. Puras, sin infraestructura."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

TIPOS_MOVIMIENTO = {
    "recepcion_compra",
    "transferencia_salida",
    "transferencia_entrada",
    "consumo_venta",
    "consumo_produccion",
    # Salida que el negocio se consume a sí mismo: hoy la comida del
    # personal (RN-COM-025). Separada de `consumo_venta` porque no tiene
    # ingreso detrás y su costo es gasto, no costo de ventas.
    "consumo_interno",
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
# `borrador` entra porque descartar la lista de la jornada es cancelarla
# (RN-INV-023): nunca reservó nada, así que liberar es un no-op, y así el
# descarte no necesita su propio camino.
ESTADOS_SOLICITUD_CANCELABLES = {"borrador", "pendiente", "aprobada"}

# Cada cuánto toca contar una categoría, en días (RN-INV-007). El período
# es en días y no en meses de calendario a propósito: el almacén cuenta
# "cada 15 días" / "cada mes", no "el mismo día de cada mes", y así el
# programa no depende de qué día tenga febrero.
# ponytail: si el negocio pide anclar al día del mes, esto pasa a
# `dateutil.relativedelta` — el resto del cálculo no cambia.
#: El tipo de artículo que **no** tiene stock (ADR-086).
#:
#: `articulo.tipo` es un enum extensible por diseño (`String(30)`, sin CHECK):
#: los tipos se agregan sin migración. Un servicio comprado —la luz, un flete,
#: un mantenimiento— es un artículo para poder ponerlo en una línea de orden
#: de compra, pero no entra a ningún almacén: no tiene SKU porque no tiene
#: existencias, no porque falte configurarlo.
#:
#: Es el discriminador y no el rol contable de su categoría, a propósito: es
#: el mismo hecho que decide si la cosa mueve stock, e `inventory` tiene que
#: poder saberlo sin preguntarle nada a `accounting`.
TIPO_SERVICIO = "servicio"

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
TIPOS_SALIDA = {
    "transferencia_salida",
    "consumo_venta",
    "consumo_produccion",
    "consumo_interno",
}
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


def cantidad_a_reponer(cantidad: Decimal, stock_minimo: Decimal | None) -> Decimal:
    """Cuánto pedir para volver al mínimo. Es una **sugerencia**: el que
    arma el requerimiento la edita.

    Sin punto de reorden ni máximo en el modelo, el mínimo es el único
    número que el negocio ya declaró. Un almacén que quedó en cero pide su
    mínimo entero; uno que quedó justo en el mínimo pide el mínimo otra vez
    —quedarse en el umbral es quedarse a un consumo de faltar—.
    """
    if stock_minimo is None:
        return Decimal(0)
    falta = stock_minimo - cantidad
    return falta if falta > 0 else stock_minimo


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


# --- Recetas condicionadas por variante (ADR-056) ----------------------------

#: Prefijo de grupo para un valor cuyo atributo no se conoce. Ver
#: `aplica_a_variante`: cada huérfano queda en su propio grupo, no todos
#: juntos en uno —que sería un O entre valores de atributos distintos—.
_GRUPO_HUERFANO = "sin-atributo:"


def aplica_a_variante(
    aplica_valores: Sequence[str] | None,
    elegidos: Sequence[str] | None,
    atributo_de: Mapping[str, str],
) -> bool:
    """¿Le toca esta línea de receta a la combinación elegida? (RN-COM-037)

    Regla de Odoo 18, literal (`mrp.bom.line._skip_bom_line` →
    `_skip_for_no_variant`): se agrupan los valores de la condición **por
    atributo**, y la combinación tiene que coincidir con **al menos uno de
    cada grupo**. Entre grupos es Y; dentro de un grupo es O.

    Es lo que hace legible el archivo real de Charlie's. La línea "Jamón
    picado" de la Pizza MitadxMitad lleva esta condición::

        Mitad 1: Americana, Mitad 1: Hawaiana, Mitad 2: Americana, Mitad 2: Hawaiana

    Son dos grupos —Mitad 1 y Mitad 2—, así que aplica cuando la primera
    mitad es Americana **u** Hawaiana **y** la segunda también. Si fuera O
    entre todo, cualquier pizza con una sola mitad americana descontaría el
    jamón de las dos.

    `aplica_valores` vacío o `None` = la línea aplica siempre. Es el caso de
    toda receta que existe hoy, y por eso la columna nace nullable: sin
    condición, el comportamiento es exactamente el de antes.

    `atributo_de` mapea `producto_atributo_valor.id` → `atributo.id`. Un
    valor que no esté en el mapa —porque alguien lo borró y la línea quedó
    apuntando a nada— forma **su propio grupo**: la línea solo aplica si la
    combinación trae ese id exacto. Es la lectura conservadora, y la que hay
    que preferir: la alternativa es descontar un insumo que quizá no va, y
    eso descuadra el conteo sin que nadie sepa por qué.
    """
    if not aplica_valores:
        return True
    disponibles = set(elegidos or ())
    if not disponibles:
        return False
    grupos: dict[str, set[str]] = {}
    for valor in aplica_valores:
        clave = atributo_de.get(valor) or f"{_GRUPO_HUERFANO}{valor}"
        grupos.setdefault(clave, set()).add(valor)
    return all(grupo & disponibles for grupo in grupos.values())


def consumo_de_linea(
    cantidad: Decimal,
    merma_pct: Decimal,
    ratio_linea: Decimal | None = None,
    ratio_articulo: Decimal | None = None,
) -> Decimal:
    """Cuánto insumo sale del almacén por una línea de receta.

    Merma más conversión de unidad, en **un solo lugar**. Estaban en dos
    —`listeners._consumos_de_items` para descontar y `recetas.costo_linea`
    para costear— escritas distinto, y dos formas de la misma cuenta
    terminan diciendo cosas distintas: el día que una gane un paréntesis, el
    costo de un plato deja de coincidir con lo que se descontó de la cámara
    y nadie sabe cuál de los dos está mal.

    Sin ratios, no convierte: es el caso de toda línea que hereda la unidad
    de su artículo, que son todas las de hoy.
    """
    base = cantidad * (Decimal(1) + merma_pct / Decimal(100))
    if ratio_linea is None or ratio_articulo is None:
        return base
    return convertir_cantidad(base, ratio_linea, ratio_articulo)


def convertir_cantidad(
    cantidad: Decimal, ratio_origen: Decimal, ratio_destino: Decimal
) -> Decimal:
    """Pasa `cantidad` de una UdM a otra de la **misma categoría** (RN-UDM-005).

    `unidad_medida.ratio` dice cuántas unidades base vale una unidad de esa
    UdM (Doypack 2 kg = ratio 2 sobre Kilo). Así que se va a la base y se
    vuelve: 30 en `ml` (ratio 0.001) son 0.03 en `L` (ratio 1).

    Sin redondear: quien llama sabe con cuántos decimales admite la unidad
    de destino (RN-GER-010) y redondea una sola vez, al final. Redondear acá
    y otra vez afuera es cómo un gramo se convierte en dos.
    """
    if ratio_destino == 0:
        raise ValueError("una unidad de medida no puede tener ratio 0")
    return cantidad * ratio_origen / ratio_destino
