"""Reglas de dominio del libro contable y del ciclo de caja: tipos de
cuenta, cuadre de asiento, qué admite un periodo según su estado
(RN-CTB-001/002), conteo por denominación (RN-POS-003/007), cadena de
custodia del efectivo (RN-MDP-002/008) y corrección de un cierre
(RN-MDP-005).
"""

from decimal import Decimal

TIPOS_CUENTA = ("activo", "pasivo", "patrimonio", "ingreso", "gasto")
_NATURALEZA_DEUDORA = {"activo", "gasto"}


def naturaleza_de_tipo(tipo: str) -> str:
    return "deudora" if tipo in _NATURALEZA_DEUDORA else "acreedora"


def cuadra(total_debe: Decimal, total_haber: Decimal) -> bool:
    return total_debe == total_haber


def puede_registrar(periodo_estado: str) -> bool:
    return periodo_estado == "abierto"


def puede_cerrar(periodo_estado: str) -> bool:
    return periodo_estado == "abierto"


def requiere_aprobacion_pago(monto: Decimal, umbral: Decimal) -> bool:
    return monto > umbral


def puede_ejecutar_pago(estado: str) -> bool:
    return estado == "pendiente"


def puede_rechazar_pago(estado: str) -> bool:
    return estado == "pendiente"


# --- Conteo por denominación (RN-POS-003/007) --------------------------------
# Billetes y monedas de curso legal en soles. El conteo se declara por pieza
# ({"50": 3, "0.50": 8}), no como un total tipeado: un total que nadie
# desglosó no es un conteo, es una afirmación.
DENOMINACIONES_PEN = (
    "200", "100", "50", "20", "10",  # billetes
    "5", "2", "1", "0.50", "0.20", "0.10",  # monedas
)


def denominaciones_desconocidas(detalle: dict) -> list[str]:
    return sorted(str(k) for k in detalle if str(k) not in DENOMINACIONES_PEN)


def total_denominaciones(detalle: dict) -> Decimal:
    """Suma del conteo. Una cantidad negativa o no entera es un error de
    tipeo, no un billete: se rechaza antes de sumar."""
    total = Decimal(0)
    for valor, cantidad in detalle.items():
        if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad < 0:
            raise ValueError(f"cantidad inválida para la denominación {valor}")
        total += Decimal(str(valor)) * cantidad
    return total


# --- Cuadre de tarjetas al cierre (RN-POS-004) ------------------------------
def pos_sin_reporte(
    pos_verificados: list | None, reportes: list | None
) -> list[str]:
    """Terminales que la apertura dio por operativos y no trajeron su
    reporte de lote al cierre.

    El cierre cuadra efectivo **y** tarjetas: sin el lote de cada terminal
    operativo, la mitad del turno queda sin verificar y un cobro mal pasado
    aparece recién en la liquidación del operador, semanas después. Un POS
    que se abrió averiado no cobró nada, así que no se le exige nada.
    """
    if not pos_verificados:
        return []
    declarados = {str(r.get("pos_tarjeta_id")) for r in (reportes or [])}
    return sorted(
        str(p["pos_tarjeta_id"])
        for p in pos_verificados
        if p.get("operativo", True) and str(p["pos_tarjeta_id"]) not in declarados
    )


def total_declarado_en_pos(reportes: list | None) -> Decimal:
    """Suma de los lotes que el cajero declaró, terminal por terminal."""
    return sum(
        (Decimal(str(r.get("monto_lote", 0))) for r in (reportes or [])), Decimal(0)
    )


# --- Cadena de custodia del efectivo (RN-MDP-002/006/008) -------------------
# El efectivo no "desaparece" al cerrar la caja: pasa de mano en mano y cada
# tramo tiene un responsable con nombre. `disponible` es el final del
# recorrido — depositado o convertido en el fondo de la siguiente apertura.
#
# El recorrido **empieza en `en_caja`** desde ADR-048: al cerrar, la plata
# sigue en el cajón a nombre del cajero, y `en_caja → en_supervisor` es la
# entrega que el encargado firma cuando pasa a buscarla. Antes la custodia
# nacía en `en_supervisor` porque el cierre ya exigía su firma; sin esa
# firma, nacer ahí sería dar por entregado lo que nadie recibió.
CUSTODIA_TRANSICIONES: dict[str, tuple[str, ...]] = {
    "en_caja": ("en_supervisor",),
    # Con caja fuerte y monto bajo el efectivo se queda en la sucursal
    # (RN-MDP-006): el encargado lo libera como fondo del día siguiente sin
    # pasar por contabilidad. Si no, lo traslada.
    "en_supervisor": ("en_contabilidad", "disponible"),
    "en_contabilidad": ("disponible",),
    "disponible": (),
}


def puede_entregar_custodia(estado_actual: str, estado_siguiente: str) -> bool:
    return estado_siguiente in CUSTODIA_TRANSICIONES.get(estado_actual, ())


# --- Corrección de un cierre (RN-MDP-005) -----------------------------------
_CIERRES_REABRIBLES = ("conforme", "con_irregularidad")


def puede_reabrir_cierre(estado_cierre: str, estado_custodia: str) -> bool:
    """Un cierre se corrige mientras el efectivo siga en el local.

    Una vez que el dinero llegó a contabilidad o se liberó, recontar el
    cajón ya no prueba nada: la corrección de ahí en adelante es un asiento
    contable, no una reapertura.

    Los dos tramos que siguen valiendo son los mismos de siempre
    (`en_caja`, `en_supervisor`), y con ADR-048 la ventana **se ensancha
    hacia el lado correcto**: el cierre recién hecho ya no salta a
    `en_supervisor`, así que recontar mientras la plata sigue en el cajón
    —el caso en que recontar de verdad prueba algo— pasó a ser el caso
    normal en vez de un estado que el sistema nunca escribía.
    """
    return (
        estado_cierre in _CIERRES_REABRIBLES
        and estado_custodia in ("en_caja", "en_supervisor")
    )
