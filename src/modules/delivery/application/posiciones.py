"""Registrar la posición GPS del repartidor mientras su ruta está en curso
(RN-DLV-007, ADR-098).

El breadcrumb (`posicion_repartidor`) es rastro sin agregación, para
auditoría; lo que lee el tablero y el enlace público es la última
posición, denormalizada en `ruta_reparto.ultima_*` — así ninguno de los
dos recorre el trazo completo en cada refresco.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.delivery.application.errors import Conflicto, NoEncontrado
from src.modules.delivery.application.parametros import parametros_de
from src.modules.delivery.domain import rules
from src.modules.delivery.infrastructure.models import Entrega, PosicionRepartidor, RutaReparto
from src.modules.users.infrastructure.models import Sucursal
from src.shared.ubicacion import metros_entre


def registrar_ping(
    session: Session,
    ruta_id: uuid.UUID,
    *,
    lat: Decimal,
    lng: Decimal,
    precision_m: int | None,
    registrado_at: datetime,
) -> RutaReparto:
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    if not rules.acepta_posicion(ruta.estado):
        raise Conflicto("la ruta no está en curso")

    session.add(
        PosicionRepartidor(
            ruta_id=ruta.id,
            repartidor_id=ruta.repartidor_id,
            lat=lat,
            lng=lng,
            precision_m=precision_m,
            registrado_at=registrado_at,
        )
    )
    ruta.ultima_lat = lat
    ruta.ultima_lng = lng
    ruta.ultima_precision_m = precision_m
    ruta.ultima_posicion_at = registrado_at

    _refrescar_eta_de_la_proxima_parada(session, ruta, lat, lng, registrado_at)
    session.flush()
    return ruta


def _proxima_parada_sin_resolver(session: Session, ruta_id: uuid.UUID) -> Entrega | None:
    """La primera parada `en_ruta` en orden de visita. Con varias paradas
    `en_ruta` a la vez (todas salen juntas al iniciar la ruta), solo la
    próxima importa: es la que el cliente que mira el enlace está viendo
    acercarse."""
    return session.scalar(
        select(Entrega)
        .where(Entrega.ruta_id == ruta_id, Entrega.estado == "en_ruta")
        .order_by(Entrega.orden_parada)
        .limit(1)
    )


def _refrescar_eta_de_la_proxima_parada(
    session: Session,
    ruta: RutaReparto,
    lat: Decimal,
    lng: Decimal,
    ahora: datetime,
) -> None:
    """Refresco barato, sin red: línea recta desde la posición nueva hasta
    el destino de la próxima parada, a la velocidad media heurística — no
    se vuelve a cotizar contra Google en cada ping (deuda declarada,
    `docs/roadmap/deuda/modulo-delivery.md`)."""
    entrega = _proxima_parada_sin_resolver(session, ruta.id)
    if entrega is None or entrega.destino_lat is None or entrega.destino_lng is None:
        return
    empresa_id = session.scalar(select(Sucursal.empresa_id).where(Sucursal.id == ruta.sucursal_id))
    parametros = parametros_de(session, empresa_id)
    distancia_directa = metros_entre(lat, lng, entrega.destino_lat, entrega.destino_lng)
    distancia_manejo = int(round(Decimal(distancia_directa) * rules.FACTOR_VIAL))
    entrega.eta_at = rules.eta_desde(ahora, distancia_manejo, parametros.velocidad_media_kmh)
