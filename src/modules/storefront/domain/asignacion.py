"""Asignación automática de local y estimado de espera (ADR-104): puro,
sin infraestructura — `application/pedidos.py` arma las `Candidata` con
datos que ya trajo de `sales`/`users` y esto solo decide.

Regla (RN-WEB-010): la sucursal más cercana dentro del radio de delivery,
salvo que esté saturada (`carga >= saturacion`) y otra candidata dentro de
ese mismo radio no lo esté — ahí se prefiere la que no está saturada, no
necesariamente la más cercana de todas. Si todas están saturadas, se manda
igual a la más cercana: mejor un pedido con más espera que uno rechazado.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

_DISTANCIA_DESCONOCIDA = Decimal("999999")


@dataclass(frozen=True)
class Candidata:
    sucursal_id: uuid.UUID
    punto_venta_id: uuid.UUID
    carga: int
    distancia_km: Decimal | None = None


def elegir(candidatas: list[Candidata], *, saturacion: int) -> Candidata | None:
    """`candidatas` ya viene filtrada a sucursales activas, con punto de
    venta web habilitado para la modalidad pedida y (para delivery) dentro
    de radio — acá solo se decide el orden entre las que quedaron.
    `None` si no queda ninguna candidata (recojo con una sola sucursal
    elegida por el cliente pasa una lista de un solo elemento)."""
    if not candidatas:
        return None
    ordenadas = sorted(
        candidatas,
        key=lambda c: c.distancia_km if c.distancia_km is not None else _DISTANCIA_DESCONOCIDA,
    )
    no_saturadas = [c for c in ordenadas if c.carga < saturacion]
    return no_saturadas[0] if no_saturadas else ordenadas[0]


#: Piso del estimado: por más que salga al instante, alguien tiene que
#: armarlo y entregarlo.
MINUTOS_MINIMOS = 5

#: Desde cuántos minutos de preparación el pedido pasa por horno y el
#: colchón es el de cocina (15) y no el de mostrador (5).
PREPARACION_DE_COCINA_MIN = 20


def estimar_eta(
    carga: int, *, preparacion_min: int, minutos_por_pedido: int, viaje_min: int = 0
) -> tuple[int, int]:
    """Rango de espera en minutos (RN-WEB-011).

    `preparacion_min` es lo que tarda **este** pedido en salir de cocina: el
    mayor tiempo entre sus productos. La cola (`carga × minutos_por_pedido`)
    solo cuenta si hay algo que cocinar: una botella de agua no espera detrás
    de las pizzas. `viaje_min` es el trayecto de un delivery.

    El rango alto agrega un colchón: 15 minutos si pasa por cocina —mismo
    criterio que los 30-45 min que Charlie's cotiza por teléfono
    (`majambo.md` §3.1.6)— y 5 si sale del mostrador.
    """
    cola = carga * minutos_por_pedido if preparacion_min > 0 else 0
    minimo = max(preparacion_min + cola + viaje_min, MINUTOS_MINIMOS)
    colchon = 15 if preparacion_min >= PREPARACION_DE_COCINA_MIN else 5
    return minimo, minimo + colchon
