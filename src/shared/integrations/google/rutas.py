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


class RutasError(RuntimeError):
    """Fallo de transporte o respuesta ilegible. Reintentable."""


@dataclass(frozen=True)
class Coordenada:
    lat: Decimal
    lng: Decimal

    def a_waypoint(self) -> dict:
        return {
            "waypoint": {
                "location": {
                    "latLng": {"latitude": float(self.lat), "longitude": float(self.lng)}
                }
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
