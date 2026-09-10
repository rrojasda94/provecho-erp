"""Distancia de manejo entre dos puntos, contra la Routes API de Google.

Único lugar del ERP que le pregunta a Google cuánto hay de un sitio a otro.
El dominio no lo llama: recibe kilómetros ya calculados y decide con ellos
(`sales.application.tarifa_delivery`).

**Esta clave no sale del servidor.** Con lo que devuelve esta llamada se le
cobra el reparto al cliente, y un número que viaja por el navegador es un
número que se puede editar. Es la razón de que sean dos claves distintas y no
una: la del mapa está restringida por dominio, esta por IP, y Google no
admite las dos restricciones en la misma clave.

Se usa `computeRouteMatrix` con una sola pareja origen/destino —que es una
matriz de 1×1— en vez del endpoint de ruta completa: la respuesta trae los
metros y nada más, sin el polilínea de la ruta, que acá no se dibuja.

`ruta_optima` sí llama al endpoint de ruta completa (`computeRoutes`) con
`optimizeWaypointOrder`: la usa el reparto propio (ADR-098) para ordenar
varias paradas de una salida y sí necesita la polilínea, para dibujar la
ruta en el tablero y en el enlace público de seguimiento.
"""

from dataclasses import dataclass
from decimal import Decimal

import httpx

from src.config.settings import settings

RUTA = "/distanceMatrix/v2:computeRouteMatrix"
# Sin esta cabecera Google responde 400: la Routes API obliga a declarar qué
# campos se quieren, y cobra distinto según lo que se pida.
CAMPOS = "originIndex,destinationIndex,distanceMeters,condition"
HAY_RUTA = "ROUTE_EXISTS"
METROS_POR_KM = Decimal("1000")

RUTA_COMPUTE = "/directions/v2:computeRoutes"
CAMPOS_RUTA = (
    "routes.optimizedIntermediateWaypointIndex,"
    "routes.distanceMeters,routes.duration,"
    "routes.legs.distanceMeters,routes.legs.duration,"
    "routes.polyline.encodedPolyline"
)


class RutasError(RuntimeError):
    """Fallo de transporte o respuesta ilegible. Reintentable."""


@dataclass(frozen=True)
class Coordenada:
    lat: Decimal
    lng: Decimal

    def a_waypoint(self) -> dict:
        return {
            "waypoint": {
                "location": {"latLng": {"latitude": float(self.lat), "longitude": float(self.lng)}}
            }
        }


def habilitado() -> bool:
    """Sin clave no se pregunta. Se consulta antes de llamar porque el que
    llama tiene una alternativa —la distancia en línea recta— y no una
    excepción que mostrarle al cajero."""
    return bool(settings.google_maps_server_key)


def distancia_km(origen: Coordenada, destino: Coordenada) -> Decimal | None:
    """Kilómetros de manejo entre los dos puntos.

    `None` cuando Google contesta pero no hay ruta: una isla, un punto en
    medio del río, una coordenada mal puesta. No es un error —la respuesta
    llegó— y quien llama decide qué hacer con un destino inalcanzable.

    Levanta `RutasError` si Google no responde o responde algo ilegible.
    """
    if not habilitado():
        raise RutasError("GOOGLE_MAPS_SERVER_KEY no configurada")
    url = settings.google_routes_base_url.rstrip("/") + RUTA
    try:
        respuesta = httpx.post(
            url,
            json={
                "origins": [origen.a_waypoint()],
                "destinations": [destino.a_waypoint()],
                "travelMode": "DRIVE",
            },
            headers={
                "X-Goog-Api-Key": settings.google_maps_server_key,
                "X-Goog-FieldMask": CAMPOS,
            },
            timeout=settings.google_timeout_segundos,
        )
    except httpx.HTTPError as e:
        raise RutasError(f"Google Routes no responde: {e}") from e
    if respuesta.status_code >= 400:
        raise RutasError(f"Google Routes devolvió {respuesta.status_code}")
    return _metros_de(respuesta)


def _metros_de(respuesta: httpx.Response) -> Decimal | None:
    try:
        cuerpo = respuesta.json()
    except ValueError as e:
        raise RutasError(f"Respuesta ilegible de Google Routes: {e}") from e
    # La matriz de 1×1 devuelve una lista de un elemento.
    elemento = cuerpo[0] if isinstance(cuerpo, list) and cuerpo else None
    if not isinstance(elemento, dict):
        raise RutasError("Google Routes devolvió una matriz vacía")
    if elemento.get("condition") != HAY_RUTA:
        return None
    metros = elemento.get("distanceMeters")
    if not isinstance(metros, int | float):
        return None
    return (Decimal(str(metros)) / METROS_POR_KM).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Tramo:
    distancia_m: int
    duracion_seg: int


@dataclass(frozen=True)
class RutaCalculada:
    #: Índices sobre la lista `paradas` que se le pasó a `ruta_optima`, en
    #: el orden en que conviene visitarlas.
    orden: list[int]
    #: Un tramo por parada visitada, del punto anterior a ella —el que
    #: sirve para el ETA de cada una. No incluye la vuelta al origen.
    tramos: list[Tramo]
    #: Distancia y duración de la salida completa, ida y vuelta al origen.
    distancia_m: int
    duracion_seg: int
    polyline: str | None


def _waypoint_de(coordenada: Coordenada) -> dict:
    return {
        "location": {
            "latLng": {
                "latitude": float(coordenada.lat),
                "longitude": float(coordenada.lng),
            }
        }
    }


def _segundos_de(valor: str | None) -> int:
    """Google devuelve la duración como texto (`"1234s"`, a veces con
    decimales). Sin valor, cero — el llamador decide qué hacer con un tramo
    sin duración, acá no es un error de transporte."""
    if not valor:
        return 0
    numero = valor[:-1] if valor.endswith("s") else valor
    try:
        return int(float(numero))
    except ValueError:
        return 0


def ruta_optima(origen: Coordenada, paradas: list[Coordenada]) -> RutaCalculada | None:
    """Orden óptimo para visitar `paradas` saliendo de `origen` y volviendo
    a él, con distancia y duración reales de manejo (ADR-098).

    Reusa la misma doctrina que `distancia_km`: la clave que calcula esto
    no sale del servidor, porque con lo que devuelve se arma la ruta que
    ve el repartidor y el ETA que ve el cliente por el enlace público.

    `None` cuando Google contesta pero no hay ruta posible (una parada
    inalcanzable) — no es un error, y quien llama tiene una alternativa (la
    heurística vecino-más-cercano) para ese caso exacto.

    Con una sola parada no se pide `optimizeWaypointOrder`: no hay nada que
    reordenar, y es un parámetro menos que Google podría rechazar.

    Levanta `RutasError` si Google no responde, responde algo ilegible, o
    la cantidad de tramos que devuelve no coincide con las paradas pedidas.
    """
    if not habilitado():
        raise RutasError("GOOGLE_MAPS_SERVER_KEY no configurada")
    if not paradas:
        raise ValueError("ruta_optima necesita al menos una parada")
    url = settings.google_routes_base_url.rstrip("/") + RUTA_COMPUTE
    cuerpo = {
        "origin": _waypoint_de(origen),
        "destination": _waypoint_de(origen),
        "intermediates": [_waypoint_de(p) for p in paradas],
        "travelMode": "DRIVE",
    }
    if len(paradas) > 1:
        cuerpo["optimizeWaypointOrder"] = True
    try:
        respuesta = httpx.post(
            url,
            json=cuerpo,
            headers={
                "X-Goog-Api-Key": settings.google_maps_server_key,
                "X-Goog-FieldMask": CAMPOS_RUTA,
            },
            timeout=settings.google_timeout_segundos,
        )
    except httpx.HTTPError as e:
        raise RutasError(f"Google Routes no responde: {e}") from e
    if respuesta.status_code >= 400:
        raise RutasError(f"Google Routes devolvió {respuesta.status_code}")
    return _ruta_de(respuesta, cantidad_paradas=len(paradas))


def _ruta_de(respuesta: httpx.Response, *, cantidad_paradas: int) -> RutaCalculada | None:
    try:
        cuerpo = respuesta.json()
    except ValueError as e:
        raise RutasError(f"Respuesta ilegible de Google Routes: {e}") from e
    rutas = cuerpo.get("routes") if isinstance(cuerpo, dict) else None
    if not rutas:
        return None
    ruta = rutas[0]
    orden = ruta.get("optimizedIntermediateWaypointIndex") or list(range(cantidad_paradas))
    legs = ruta.get("legs") or []
    # La última pierna es la vuelta al origen: cuenta para el total de la
    # salida (abajo) pero no es el tramo de ninguna parada.
    tramos = [
        Tramo(
            distancia_m=leg.get("distanceMeters", 0),
            duracion_seg=_segundos_de(leg.get("duration")),
        )
        for leg in legs[:cantidad_paradas]
    ]
    if len(tramos) != cantidad_paradas:
        raise RutasError(
            f"Google Routes devolvió {len(tramos)} tramos para {cantidad_paradas} paradas"
        )
    return RutaCalculada(
        orden=list(orden),
        tramos=tramos,
        distancia_m=ruta.get("distanceMeters", 0),
        duracion_seg=_segundos_de(ruta.get("duration")),
        polyline=(ruta.get("polyline") or {}).get("encodedPolyline"),
    )
