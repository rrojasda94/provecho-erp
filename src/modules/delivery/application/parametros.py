"""Parámetros operativos de `delivery` configurables por empresa (ADR-014).

Solo dos, y los dos con semilla en `settings` como respaldo — mismo
criterio que `sales.application.tarifa_delivery.tarifa_de`: una empresa
que no aprobó nada todavía sigue operando con el valor por defecto, nunca
bloqueada por falta de configuración.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.delivery.domain import rules
from src.shared import parametros

MODULO = "delivery"
CODIGO_MAX_PARADAS = "max_paradas_ruta"
CODIGO_VELOCIDAD_MEDIA = "velocidad_media_kmh"


@dataclass(frozen=True)
class ParametrosReparto:
    max_paradas_ruta: int
    velocidad_media_kmh: Decimal


def _semilla() -> ParametrosReparto:
    return ParametrosReparto(
        max_paradas_ruta=settings.delivery_max_paradas_ruta,
        velocidad_media_kmh=settings.delivery_velocidad_media_kmh,
    )


def parametros_de(session: Session, empresa_id: uuid.UUID | None) -> ParametrosReparto:
    semilla = _semilla()
    if empresa_id is None:
        return semilla

    max_paradas = parametros.valor_vigente(
        session, empresa_id, MODULO, CODIGO_MAX_PARADAS, semilla.max_paradas_ruta
    )
    velocidad = parametros.valor_vigente(
        session, empresa_id, MODULO, CODIGO_VELOCIDAD_MEDIA, semilla.velocidad_media_kmh
    )
    try:
        max_paradas_int = int(max_paradas)
    except (TypeError, ValueError):
        max_paradas_int = semilla.max_paradas_ruta
    try:
        velocidad_dec = Decimal(str(velocidad))
    except Exception:
        velocidad_dec = semilla.velocidad_media_kmh
    if max_paradas_int < 1:
        max_paradas_int = rules.MAX_PARADAS_DEFECTO
    if velocidad_dec <= 0:
        velocidad_dec = semilla.velocidad_media_kmh
    return ParametrosReparto(max_paradas_ruta=max_paradas_int, velocidad_media_kmh=velocidad_dec)
