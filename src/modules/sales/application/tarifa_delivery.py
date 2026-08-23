"""Cuánto cuesta llevar un pedido, y cuándo conviene no llevarlo (ADR-054).

Tres respuestas en una sola pregunta:

- **Cuánto se cobra** — tarifa base más precio por kilómetro de manejo real,
  no en línea recta: un río en el medio son dos kilómetros de puente.
- **Si el reparto propio llega** — pasado el radio configurado, el pedido
  sale más barato derivándolo a una plataforma externa (DAZ DAZ) que
  mandando a alguien media hora en moto.
- **Si la zona está vetada** — hay distritos donde el negocio decidió no
  repartir. Se resuelve por nombre de distrito, que ya viene con la
  dirección, y no con polígonos: PostGIS es mucha máquina para una lista de
  cuatro nombres.

**Se calcula en el servidor y nada más que en el servidor.** Define cuánta
plata paga el cliente; un número calculado en el navegador es un número que
se puede editar.

**Nunca bloquea una venta.** Si Google no contesta se cae a la distancia en
línea recta y la cotización se marca `aproximada`: cobrar de menos por un
kilómetro es preferible a no poder tomar el pedido. Es además lo único que
funciona en el hub offline de una sucursal (ADR-009).
"""

import math
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from src.config.settings import settings
from src.shared.integrations.google import Coordenada, RutasError, distancia_km

# Radio terrestre medio. La fórmula del círculo máximo alcanza de sobra para
# una ciudad: el error contra la distancia de manejo lo domina el trazado de
# las calles, no la curvatura.
RADIO_TIERRA_KM = 6371.0
# Lo que camina de más un reparto urbano respecto de la línea recta. Es un
# factor de calibración, no una constante universal: en Tarapoto las calles
# son bastante regulares, en un cerro sería más. Se ajusta comparando unas
# cuantas cotizaciones aproximadas contra las reales de Google.
FACTOR_CALLE = Decimal("1.3")

MOTIVO_FUERA_DE_RADIO = "fuera_de_radio"
MOTIVO_ZONA_RESTRINGIDA = "zona_restringida"


@dataclass(frozen=True)
class Cotizacion:
    """Lo que el cajero necesita saber antes de aceptar un delivery."""

    distancia_km: Decimal | None
    costo: Decimal
    # True cuando la distancia salió de la línea recta y no de Google: el PDV
    # lo muestra como "aprox." para que nadie discuta el monto como si fuera
    # una medición.
    aproximada: bool
    derivar_a_externo: bool
    motivo: str | None = None


def _sin_tildes(texto: str) -> str:
    """`Belén` y `Belen` son el mismo distrito. Lo que llega de Google y lo
    que alguien tecleó en el `.env` no tienen por qué coincidir en tildes."""
    plano = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in plano if unicodedata.category(c) != "Mn").strip().lower()


def zona_restringida(distrito: str | None) -> bool:
    if not distrito:
        return False
    vetados = {_sin_tildes(d) for d in settings.delivery_distritos_restringidos}
    return _sin_tildes(distrito) in vetados


def linea_recta_km(origen: Coordenada, destino: Coordenada) -> Decimal:
    """Haversine, corregido por `FACTOR_CALLE`. Es el plan B cuando no hay
    Google: seis líneas y ninguna dependencia nueva."""
    lat1, lng1 = math.radians(float(origen.lat)), math.radians(float(origen.lng))
    lat2, lng2 = math.radians(float(destino.lat)), math.radians(float(destino.lng))
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    recta = Decimal(str(RADIO_TIERRA_KM * 2 * math.asin(math.sqrt(a))))
    return (recta * FACTOR_CALLE).quantize(Decimal("0.01"))


def costo_de(distancia: Decimal | None) -> Decimal:
    """Tarifa base más el tramo por kilómetro. Con la configuración en cero
    —el estado de fábrica— devuelve cero y el delivery se sigue cobrando como
    antes de todo esto."""
    base = settings.delivery_tarifa_base
    if distancia is None:
        return base
    por_km = settings.delivery_precio_por_km * distancia
    return (base + por_km).quantize(Decimal("0.01"))


# 5 decimales ~ 1 m: dos pedidos a la misma puerta comparten entrada. Sin
# TTL a propósito —la distancia entre dos puntos fijos no cambia— y sin
# Redis: un diccionario por proceso alcanza, y lo que se ahorra es la segunda
# llamada por pedido (la que cotiza el cajero y la que congela la orden).
#
# Va sobre `distancia_km` y no sobre `_medir` para que un fallo de Google NO
# quede cacheado: `lru_cache` no guarda excepciones, así que la estimación en
# línea recta se recalcula cada vez y la medición real vuelve sola en cuanto
# Google responde.
_TOPE_CACHE = 2048
_PRECISION = 5


@lru_cache(maxsize=_TOPE_CACHE)
def _distancia_cacheada(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> Decimal | None:
    return distancia_km(
        Coordenada(Decimal(str(lat1)), Decimal(str(lng1))),
        Coordenada(Decimal(str(lat2)), Decimal(str(lng2))),
    )


def _medir(origen: Coordenada, destino: Coordenada) -> tuple[Decimal | None, bool]:
    """Kilómetros y si el número es aproximado."""
    try:
        exacta = _distancia_cacheada(
            round(float(origen.lat), _PRECISION),
            round(float(origen.lng), _PRECISION),
            round(float(destino.lat), _PRECISION),
            round(float(destino.lng), _PRECISION),
        )
    except RutasError:
        # Google caído, sin clave o sin cuota. El pedido se toma igual.
        return linea_recta_km(origen, destino), True
    if exacta is None:
        # Contestó, pero no hay ruta manejable hasta ahí.
        return None, False
    return exacta, False


def cotizar(
    origen: Coordenada | None,
    destino: Coordenada | None,
    distrito_destino: str | None = None,
) -> Cotizacion:
    """Cotiza el reparto de la sucursal `origen` al `destino` del cliente.

    Sin alguno de los dos puntos —una sucursal que nadie ancló todavía, una
    dirección escrita a mano— devuelve la tarifa base sin distancia. No es un
    error: es el estado normal el día que esto se enciende, y la alternativa
    sería no poder cobrar el delivery hasta terminar de anclar el mapa.
    """
    if zona_restringida(distrito_destino):
        # Antes de medir: la zona vetada no depende de la distancia y
        # preguntarle a Google costaría una llamada por una respuesta que ya
        # se sabe.
        return Cotizacion(
            distancia_km=None,
            costo=settings.delivery_tarifa_base,
            aproximada=False,
            derivar_a_externo=True,
            motivo=MOTIVO_ZONA_RESTRINGIDA,
        )
    if origen is None or destino is None:
        return Cotizacion(None, settings.delivery_tarifa_base, False, False)

    distancia, aproximada = _medir(origen, destino)
    if distancia is None:
        return Cotizacion(
            distancia_km=None,
            costo=settings.delivery_tarifa_base,
            aproximada=False,
            derivar_a_externo=True,
            motivo=MOTIVO_FUERA_DE_RADIO,
        )

    maxima = settings.delivery_distancia_maxima_km
    fuera = bool(maxima) and distancia > maxima
    return Cotizacion(
        distancia_km=distancia,
        costo=costo_de(distancia),
        aproximada=aproximada,
        derivar_a_externo=fuera,
        motivo=MOTIVO_FUERA_DE_RADIO if fuera else None,
    )


def coordenada(lat: Decimal | None, lng: Decimal | None) -> Coordenada | None:
    """Las dos o ninguna: media coordenada no es un punto."""
    if lat is None or lng is None:
        return None
    return Coordenada(lat, lng)


def origen_de_sucursal(session, sucursal_id) -> Coordenada | None:
    """Desde donde sale el reparto.

    `None` si la sucursal todavía no está anclada en el mapa, que es el
    estado de todas el día que esto se despliega. La cotización sigue
    andando: devuelve la tarifa base sin distancia, y nadie se queda sin
    poder vender por una ficha a medio llenar.
    """
    from src.modules.users.infrastructure.models import Sucursal

    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None:
        return None
    return coordenada(sucursal.ubicacion_lat, sucursal.ubicacion_lng)
