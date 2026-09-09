"""Contrato público de lectura de `assets` para otros módulos.

Mismo criterio que `inventory.application.queries_publicas`: único punto de
entrada para que otro módulo lea datos de `assets`, devolviendo DTOs
(dicts), nunca el ORM. Nadie importa `assets.infrastructure` desde afuera.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.assets.infrastructure.models import Activo
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


def activos_depreciables(session: Session, empresa_id: uuid.UUID | None = None) -> list[dict]:
    """Activos con lo que hace falta para depreciar: `valor_compra`,
    `vida_util_meses` y `fecha_compra`, los tres NOT NULL. `empresa_id=None`
    trae los de todas — el barrido mensual de `accounting` los agrupa por
    empresa después, igual que `assets.avisos.barrer` con sus planes.

    Un activo `de_baja` no acumula más depreciación (RN-ACT, deuda de
    `accounting`): sigue existiendo para consulta, pero deja de aparecer acá.
    """
    q = select(Activo).where(
        Activo.deleted_at.is_(None),
        Activo.estado != "de_baja",
        Activo.valor_compra.is_not(None),
        Activo.vida_util_meses.is_not(None),
        Activo.fecha_compra.is_not(None),
    )
    if empresa_id is not None:
        q = q.where(Activo.empresa_id == empresa_id)
    return [
        {
            "id": a.id,
            "empresa_id": a.empresa_id,
            "nombre": a.nombre,
            "valor_compra": a.valor_compra,
            "vida_util_meses": a.vida_util_meses,
            "fecha_compra": a.fecha_compra,
        }
        for a in session.scalars(q)
    ]
