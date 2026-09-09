"""Reglas de negocio de reparto propio. Puras, sin infraestructura (ADR-098).

Nada de acá importa `src.shared` ni `src.core`: la heurística de ruteo
recibe la función de distancia como parámetro (`test_arquitectura.py`
prohíbe que `domain/` dependa de nada fuera del propio módulo).
"""

from datetime import datetime, timedelta
from decimal import Decimal

VEHICULOS = ("moto", "bicicleta", "auto", "a_pie")

ESTADOS_ENTREGA = (
    "pendiente",
    "asignada",
    "en_ruta",
    "entregada",
    "fallida",
    "cancelada",
)
ESTADOS_RUTA = ("planificada", "en_curso", "finalizada", "cancelada")
MOTIVOS_FALLO = ("cliente_ausente", "direccion_errada", "rechazo", "no_contesta", "otro")
FUENTES_RUTEO = ("google", "heuristica", "manual")

#: La línea recta subestima lo que de verdad se maneja: una calle rara vez
#: es la hipotenusa. 1.3 es la misma corrección que ya usa la cotización de
#: delivery de `sales` (`tarifa_delivery.aproximada`) cuando Google no
#: contesta — mismo criterio, para no inventar un segundo factor.
FACTOR_VIAL = Decimal("1.3")

#: Techo por defecto de paradas en una ruta, si la empresa no configuró
#: `delivery_max_paradas_ruta` en `parametro_empresa` (ADR-014). Una ruta
#: sin techo es un repartidor con la mochila llena de pedidos fríos.
MAX_PARADAS_DEFECTO = 10


def motivo_requiere_detalle(motivo: str) -> bool:
    """RN-CUP-008/RN-DLV-003: "otro" no dice nada por sí solo — sin detalle,
    el encargado no tiene con qué decidir devolución, reintento o merma."""
    return motivo == "otro"


def cantidad_de_paradas_valida(cantidad: int, limite: int) -> bool:
    """RN-DLV-002/005: una ruta lleva al menos una parada y no más que el
    límite configurado (o el techo por defecto, si no hay parámetro)."""
    return 1 <= cantidad <= limite


# --- Transiciones de `entrega` (RN-DLV-001/003/004/006) ----------------------


def puede_asignar_a_ruta(estado: str) -> bool:
    return estado == "pendiente"


def puede_desasignar(estado: str) -> bool:
    """Quitar una parada de una ruta que no salió todavía la devuelve al
    montón de pendientes — no es un fallo, es que no le tocaba esta vuelta."""
    return estado == "asignada"


def puede_marcar_en_ruta(estado: str) -> bool:
    return estado == "asignada"


def puede_entregar(estado: str) -> bool:
    return estado == "en_ruta"


def puede_fallar(estado: str) -> bool:
    return estado == "en_ruta"


def puede_reintentar(estado: str) -> bool:
    return estado == "fallida"


def puede_cerrar_entrega(estado: str) -> bool:
    """Cerrar sin reintentar: de `fallida` (se decide no reintentar) o de
    `pendiente` (ya no hace falta reparto propio para ese pedido)."""
    return estado in ("fallida", "pendiente")


def cancela_sola_por_anulacion(estado: str) -> bool:
    """RN-DLV-006: una venta anulada cancela su entrega sola solo si
    todavía no salió a la calle. `en_ruta` no se toca acá — el repartidor
    puede estar a mitad de camino y decide el despacho, no un evento."""
    return estado in ("pendiente", "asignada")


# --- Transiciones de `ruta_reparto` (RN-DLV-005) -----------------------------


def puede_iniciar_ruta(estado: str, cantidad_paradas: int) -> bool:
    return estado == "planificada" and cantidad_paradas >= 1


def puede_editar_paradas(estado: str) -> bool:
    return estado == "planificada"


def puede_cancelar_ruta(estado: str) -> bool:
    return estado == "planificada"


def puede_finalizar_ruta(estado_ruta: str, estados_entregas: list[str]) -> bool:
    """Todas las paradas resueltas —entregada, fallida o cancelada—, nunca
    con una entrega todavía `en_ruta` colgando."""
    if estado_ruta != "en_curso":
        return False
    return all(e in ("entregada", "fallida", "cancelada") for e in estados_entregas)


# --- Posición del repartidor (RN-DLV-007) ------------------------------------


def acepta_posicion(estado_ruta: str) -> bool:
    """El GPS solo se acepta mientras la ruta está en curso: antes no hay
    nada que mostrar, y después el trazo ya se cerró."""
    return estado_ruta == "en_curso"


def expone_posicion(estado_entrega: str) -> bool:
    """Se muestra —tablero o enlace público— solo mientras esa parada
    puntual sigue en camino. Entregada, fallida o cancelada: se apaga."""
    return estado_entrega == "en_ruta"


# --- Ruteo: heurística sin red (RN-DLV-002) ----------------------------------


def ordenar_vecino_mas_cercano(origen, paradas: list, distancia) -> list[int]:
    """Orden de índices de `paradas` que visita, en cada paso, la más
    cercana al punto donde se está parado — golosa, no óptima, pero no
    necesita red ni clave: es lo único que puede correr en el hub offline
    de una sucursal (ADR-009) o cuando Google no responde.

    `distancia(a, b)` es cualquier función de distancia entre dos puntos
    (mismo tipo que `origen` y los elementos de `paradas`); quien llama
    decide cuál — acá no se importa nada de fuera del módulo.
    """
    pendientes = list(range(len(paradas)))
    orden: list[int] = []
    actual = origen
    while pendientes:
        siguiente = min(pendientes, key=lambda i: distancia(actual, paradas[i]))
        orden.append(siguiente)
        actual = paradas[siguiente]
        pendientes.remove(siguiente)
    return orden


def eta_por_parada(hora_salida: datetime, duraciones_seg: list[int]) -> list[datetime]:
    """ETA acumulado de cada parada, sumando el tramo hasta llegar a ella.

    No es la duración de *ir* a la parada aislada: es la hora real a la que
    se llega después de las paradas anteriores — por eso acumula y no
    reporta cada tramo por separado.
    """
    acumulado = hora_salida
    etas = []
    for duracion in duraciones_seg:
        acumulado = acumulado + timedelta(seconds=duracion)
        etas.append(acumulado)
    return etas


def duracion_heuristica_seg(distancia_m: int, velocidad_media_kmh: Decimal) -> int:
    """Cuánto tarda un tramo sin preguntarle a nadie: distancia sobre una
    velocidad media configurable (`delivery_velocidad_media_kmh`). Grosero
    a propósito — es el mismo trato que la cotización de delivery le da a
    la línea recta cuando Google no contesta."""
    if velocidad_media_kmh <= 0:
        return 0
    horas = (Decimal(distancia_m) / Decimal(1000)) / velocidad_media_kmh
    return round(horas * 3600)


def eta_desde(
    ahora: datetime,
    distancia_m: int,
    velocidad_media_kmh: Decimal,
) -> datetime:
    """Refresco barato del ETA de la parada siguiente, en cada ping de GPS
    (RN-DLV — sin re-cotizar contra Google en cada posición, que es deuda
    declarada): la distancia en línea recta desde donde está el repartidor
    ahora hasta el destino, a la misma velocidad media heurística que usa
    el resto del ruteo sin red.
    """
    return ahora + timedelta(seconds=duracion_heuristica_seg(distancia_m, velocidad_media_kmh))
