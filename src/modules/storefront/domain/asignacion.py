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


def estimar_eta(
    carga: int, *, base_minutos: int, minutos_por_pedido: int
) -> tuple[int, int]:
    """Rango de espera en minutos: `base` sin cola, `+minutos_por_pedido`
    por cada pedido `orden` que la sucursal ya tiene delante del suyo
    (RN-WEB-011). El rango alto agrega 15 minutos de colchón — mismo
    criterio que los 30-45/45-55 min que Charlie's ya cotiza por teléfono
    (`majambo.md` §3.1.6)."""
    minimo = base_minutos + carga * minutos_por_pedido
    return minimo, minimo + 15
