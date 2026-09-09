"""Cálculo del orden de paradas y sus tiempos (ADR-098).

`optimizar=True` intenta primero la Routes API de Google
(`optimizeWaypointOrder`, con la polilínea real de la ruta) y cae a la
heurística vecino-más-cercano si Google no está configurado, no responde,
o no encuentra ruta a alguna parada — nunca bloquea crear la ruta por un
proveedor externo caído (mismo criterio que
`sales.application.tarifa_delivery` con la cotización de delivery).
`optimizar=False` respeta el orden dado (`PUT /rutas/{id}/paradas` a
mano) y usa la heurística solo para estimar distancia/duración, sin
polilínea.

Reusa `Coordenada` de `shared/integrations/google`: son el mismo punto
(lat, lng), y dos tipos para lo mismo solo pedirían traducir entre ellos
en cada llamada.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

from src.modules.delivery.application.parametros import ParametrosReparto
from src.modules.delivery.domain import rules
from src.shared.integrations.google import Coordenada, RutasError
from src.shared.integrations.google import habilitado as google_habilitado
from src.shared.integrations.google import ruta_optima as google_ruta_optima
from src.shared.ubicacion import metros_entre

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tramo:
    distancia_m: int
    duracion_seg: int


@dataclass(frozen=True)
class PlanRuta:
    #: Índices de `paradas`, en el orden a visitar.
    orden: list[int]
    #: Un tramo por parada, en ese mismo orden — del punto anterior a ella.
    #: No incluye la vuelta al origen.
    tramos: list[Tramo]
    #: Distancia y duración de la salida completa, ida y vuelta al origen.
    distancia_m: int
    duracion_seg: int
    polyline: str | None
    #: "google" | "heuristica" | "manual" — con qué se calculó, no si el
    #: pedido fue optimizar (una ruta puede pedir Google y caer a
    #: heurística si el proveedor no responde).
    fuente: str


def _distancia_m(a: Coordenada, b: Coordenada) -> int:
    return metros_entre(a.lat, a.lng, b.lat, b.lng)


def planificar(
    origen: Coordenada,
    paradas: list[Coordenada],
    *,
    optimizar: bool,
    parametros: ParametrosReparto,
) -> PlanRuta:
    """El orden de paradas y cuánto toma cada tramo."""
    if optimizar and paradas and google_habilitado():
        calculada = _intentar_google(origen, paradas)
        if calculada is not None:
            return calculada
    return _planificar_heuristica(origen, paradas, optimizar=optimizar, parametros=parametros)


def _intentar_google(origen: Coordenada, paradas: list[Coordenada]) -> PlanRuta | None:
    try:
        calculada = google_ruta_optima(origen, paradas)
    except RutasError:
        log.warning("Google Routes no respondió, se rutea por heurística", exc_info=True)
        return None
    if calculada is None:
        # Google contestó pero no hay ruta a alguna parada (un punto
        # inalcanzable): la heurística sigue siendo mejor que no rutear.
        return None
    return PlanRuta(
        orden=calculada.orden,
        tramos=[Tramo(t.distancia_m, t.duracion_seg) for t in calculada.tramos],
        distancia_m=calculada.distancia_m,
        duracion_seg=calculada.duracion_seg,
        polyline=calculada.polyline,
        fuente="google",
    )


def _planificar_heuristica(
    origen: Coordenada,
    paradas: list[Coordenada],
    *,
    optimizar: bool,
    parametros: ParametrosReparto,
) -> PlanRuta:
    if optimizar:
        orden = rules.ordenar_vecino_mas_cercano(origen, paradas, _distancia_m)
        fuente = "heuristica"
    else:
        orden = list(range(len(paradas)))
        fuente = "manual"

    tramos: list[Tramo] = []
    anterior = origen
    for indice in orden:
        parada = paradas[indice]
        tramos.append(_tramo_heuristico(anterior, parada, parametros))
        anterior = parada
    # Vuelta al origen: cuenta para el total de la salida, no es el tramo
    # de ninguna parada (mismo criterio que Google, que siempre cotiza la
    # ruta redonda al pedir `destination = origin`).
    vuelta = _tramo_heuristico(anterior, origen, parametros) if paradas else None

    distancia_total = sum(t.distancia_m for t in tramos) + (vuelta.distancia_m if vuelta else 0)
    duracion_total = sum(t.duracion_seg for t in tramos) + (vuelta.duracion_seg if vuelta else 0)
    return PlanRuta(
        orden=orden,
        tramos=tramos,
        distancia_m=distancia_total,
        duracion_seg=duracion_total,
        polyline=None,
        fuente=fuente,
    )


def _tramo_heuristico(a: Coordenada, b: Coordenada, parametros: ParametrosReparto) -> Tramo:
    distancia_directa = _distancia_m(a, b)
    distancia_manejo = int(round(Decimal(distancia_directa) * rules.FACTOR_VIAL))
    duracion = rules.duracion_heuristica_seg(distancia_manejo, parametros.velocidad_media_kmh)
    return Tramo(distancia_m=distancia_manejo, duracion_seg=duracion)
