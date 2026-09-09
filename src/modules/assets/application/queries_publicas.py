"""Contrato público de lectura de `assets` para otros módulos.

Mismo criterio que `inventory.application.queries_publicas`: único punto de
entrada para que otro módulo lea datos de `assets`, devolviendo DTOs
(dicts), nunca el ORM. Nadie importa `assets.infrastructure` desde afuera.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.assets.infrastructure.repositories import ActivoRepo, VehiculoRepo


def vehiculo_para_guia(session: Session, vehiculo_id: uuid.UUID) -> dict | None:
    """Placa y empresa de un vehículo, para que `inventory` lo declare en una
    guía de remisión sin importar el dominio de `assets`. `None` si no
    existe (`vehiculo_id` es el mismo `activo_id`, la relación es 1:1)."""
    vehiculo = VehiculoRepo(session).get(vehiculo_id)
    if vehiculo is None:
        return None
    activo = ActivoRepo(session).get(vehiculo.activo_id)
    return {
        "id": vehiculo.activo_id,
        "placa": vehiculo.placa,
        "empresa_id": activo.empresa_id if activo else None,
    }
