"""Lectura de umbrales de la matriz de aprobaciones (`regla_aprobacion`).
Único punto que los módulos operativos deben consultar en vez de hardcodear
su propio umbral (RN-GER-003)."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.shared.repositories import ReglaAprobacionRepo


def umbral_vigente(
    session: Session,
    empresa_id: uuid.UUID,
    modulo: str,
    codigo: str,
    default: Decimal,
) -> Decimal:
    """Umbral configurado para `empresa_id`/`modulo`/`codigo`, o `default`
    (valor semilla del propio módulo) si nadie lo configuró todavía."""
    regla = ReglaAprobacionRepo(session).get_vigente(empresa_id, modulo, codigo)
    return regla.umbral if regla is not None else default
