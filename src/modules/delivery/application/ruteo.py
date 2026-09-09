"""Cálculo del orden de paradas y sus tiempos, sin red (ADR-098).

Slice 2: solo la heurística vecino-más-cercano (`domain.rules`), sin
Google. El ruteo real contra `computeRoutes` (con `optimizeWaypointOrder`)
llega en el slice siguiente y se conecta acá — la firma de `planificar` ya
está pensada para eso: hoy `optimizar=True` usa la misma heurística que
`optimizar=False` con otro orden, y ese es exactamente el `if` que el
slice de ruteo real va a completar con un intento contra la Routes API
antes de caer a esto.

Reusa `Coordenada` de `shared/integrations/google`: son el mismo punto
(lat, lng) y usar dos tipos para la misma cosa solo pediría traducir entre
ellos cuando llegue el ruteo real.
"""

from dataclasses import dataclass
from decimal import Decimal

from src.modules.delivery.application.parametros import ParametrosReparto
from src.modules.delivery.domain import rules
from src.shared.integrations.google import Coordenada
from src.shared.ubicacion import metros_entre


@dataclass(frozen=True)
class Tramo:
    distancia_m: int
    duracion_seg: int


@dataclass(frozen=True)
class PlanRuta:
    #: Índices de `paradas`, en el orden a visitar.
    orden: list[int]
    #: Un tramo por parada, en ese mismo orden — del punto anterior a ella.
    tramos: list[Tramo]
    distancia_m: int
    duracion_seg: int
    polyline: str | None
    #: "heuristica" | "manual" (| "google", desde el slice de ruteo real).
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
    """El orden de paradas y cuánto toma cada tramo.

    `optimizar=False` respeta el orden en que llegaron las paradas —lo que
    pide `PUT /rutas/{id}/paradas` al reordenar a mano—; `optimizar=True`
    aplica la heurística vecino-más-cercano. Ninguno de los dos llama a
    Google todavía.
    """
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
        distancia_directa = _distancia_m(anterior, parada)
        distancia_manejo = int(round(Decimal(distancia_directa) * rules.FACTOR_VIAL))
        duracion = rules.duracion_heuristica_seg(distancia_manejo, parametros.velocidad_media_kmh)
        tramos.append(Tramo(distancia_m=distancia_manejo, duracion_seg=duracion))
        anterior = parada

    return PlanRuta(
        orden=orden,
        tramos=tramos,
        distancia_m=sum(t.distancia_m for t in tramos),
        duracion_seg=sum(t.duracion_seg for t in tramos),
        polyline=None,
        fuente=fuente,
    )
