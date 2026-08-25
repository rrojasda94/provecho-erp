"""Cuánto cuesta llevar un pedido, y cuándo conviene no llevarlo (ADR-054).

Tres respuestas en una sola pregunta:

- **Cuánto se cobra** — tarifa base más precio por kilómetro de manejo real,
  no en línea recta: un río en el medio son dos kilómetros de puente. Los dos
  números los aprueba Gerencia por empresa (ADR-014), no los define el `.env`:
  es un precio, y un precio no puede depender de quién tiene acceso al
  servidor. `settings` queda como valor de arranque.
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
import uuid
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.shared.integrations.google import Coordenada, RutasError, distancia_km
from src.shared.parametros import valor_vigente

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

# Códigos de los parámetros que Gerencia aprueba por empresa (ADR-014). Son
# tres y no uno compuesto porque el formulario de propuesta arma un solo valor
# por vez (`gerencia/actions.ts`): un compuesto solo se podría sembrar, y el
# punto de esto es justamente que la tarifa se cambie sin tocar el servidor.
CODIGO_TARIFA_BASE = "delivery_tarifa_base"
CODIGO_PRECIO_POR_KM = "delivery_precio_por_km"
CODIGO_DISTANCIA_MAXIMA = "delivery_distancia_maxima_km"


@dataclass(frozen=True)
class Tarifa:
    """Con cuánto se cobra este reparto. Se resuelve una vez, antes de medir.

    Existe para que `cotizar` no lea configuración global: lo que se cobra
    depende de la empresa dueña de la sucursal, y una función que va a buscar
    el precio a `settings` no puede cobrarle distinto a dos empresas.
    """

    base: Decimal
    por_km: Decimal
    maxima_km: Decimal

    @classmethod
    def de_settings(cls) -> "Tarifa":
        """El valor de arranque: rige mientras Gerencia no apruebe el suyo.
        En cero —el estado de fábrica— el reparto no cobra nada."""
        return cls(
            base=settings.delivery_tarifa_base,
            por_km=settings.delivery_precio_por_km,
            maxima_km=settings.delivery_distancia_maxima_km,
        )


def _numero(valor: object, clave: str, default: Decimal) -> Decimal:
    """Saca la magnitud del JSON del parámetro. Un valor con otra forma —una
    propuesta vieja, un código reusado— cae al default en vez de reventar la
    venta: el reparto se cobra de más o de menos, pero el pedido se toma."""
    if not isinstance(valor, dict) or valor.get(clave) is None:
        return default
    try:
        return Decimal(str(valor[clave]))
    except ArithmeticError:
        return default


def tarifa_de_empresa(session: Session, empresa_id: uuid.UUID | None) -> Tarifa:
    """Lo que Gerencia aprobó para esta empresa, con `settings` como default.

    Mismo criterio que `inventory/margenes.py`: el valor de `settings` deja de
    ser la regla y pasa a ser el punto de partida. Sin empresa —una sucursal
    que no resolvió su dueño— no hay a quién preguntarle: rige el arranque.
    """
    arranque = Tarifa.de_settings()
    if empresa_id is None:
        return arranque

    def _param(codigo: str, clave: str, default: Decimal) -> Decimal:
        return _numero(
            valor_vigente(session, empresa_id, "sales", codigo), clave, default
        )

    return Tarifa(
        base=_param(CODIGO_TARIFA_BASE, "monto", arranque.base),
        por_km=_param(CODIGO_PRECIO_POR_KM, "monto", arranque.por_km),
        maxima_km=_param(CODIGO_DISTANCIA_MAXIMA, "kilometros", arranque.maxima_km),
    )


def empresa_de_sucursal(session: Session, sucursal_id: uuid.UUID) -> uuid.UUID | None:
    """Quién cobra este reparto. La tarifa es por empresa y lo que se tiene a
    mano al cotizar es la sucursal (mismo salto que `sales/alertas.py`)."""
    from src.modules.users.infrastructure.models import Sucursal

    return session.scalar(
        select(Sucursal.empresa_id).where(Sucursal.id == sucursal_id)
    )


def tarifa_de_sucursal(session: Session, sucursal_id: uuid.UUID) -> Tarifa:
    """Atajo para los dos únicos llamadores, que siempre parten de la sucursal."""
    return tarifa_de_empresa(session, empresa_de_sucursal(session, sucursal_id))


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


def costo_de(distancia: Decimal | None, tarifa: Tarifa) -> Decimal:
    """Tarifa base más el tramo por kilómetro. Con la tarifa en cero —el
    estado de fábrica— devuelve cero y el delivery se sigue cobrando como
    antes de todo esto."""
    if distancia is None:
        return tarifa.base
    return (tarifa.base + tarifa.por_km * distancia).quantize(Decimal("0.01"))


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
    tarifa: Tarifa | None = None,
) -> Cotizacion:
    """Cotiza el reparto de la sucursal `origen` al `destino` del cliente.

    Sin alguno de los dos puntos —una sucursal que nadie ancló todavía, una
    dirección escrita a mano— devuelve la tarifa base sin distancia. No es un
    error: es el estado normal el día que esto se enciende, y la alternativa
    sería no poder cobrar el delivery hasta terminar de anclar el mapa.

    `tarifa` sin pasar cae al valor de arranque de `settings`. Quien cobra de
    verdad la resuelve antes con `tarifa_de_sucursal`: el precio es de la
    empresa, no del despliegue (ADR-014).
    """
    tarifa = tarifa or Tarifa.de_settings()
    if zona_restringida(distrito_destino):
        # Antes de medir: la zona vetada no depende de la distancia y
        # preguntarle a Google costaría una llamada por una respuesta que ya
        # se sabe.
        return Cotizacion(
            distancia_km=None,
            costo=tarifa.base,
            aproximada=False,
            derivar_a_externo=True,
            motivo=MOTIVO_ZONA_RESTRINGIDA,
        )
    if origen is None or destino is None:
        return Cotizacion(None, tarifa.base, False, False)

    distancia, aproximada = _medir(origen, destino)
    if distancia is None:
        return Cotizacion(
            distancia_km=None,
            costo=tarifa.base,
            aproximada=False,
            derivar_a_externo=True,
            motivo=MOTIVO_FUERA_DE_RADIO,
        )

    fuera = bool(tarifa.maxima_km) and distancia > tarifa.maxima_km
    return Cotizacion(
        distancia_km=distancia,
        costo=costo_de(distancia, tarifa),
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
