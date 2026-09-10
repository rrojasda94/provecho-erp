"""Repuestos compatibles con un activo — catálogo de sugerencias, no bloquea
el registro de repuestos en una orden de mantenimiento."""

import uuid

from sqlalchemy.orm import Session

from src.modules.assets.application.errors import Conflicto, NoEncontrado
from src.modules.assets.infrastructure.models import RepuestoCompatibilidad
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    RepuestoCompatibilidadRepo,
)


def agregar_compatible(
    session: Session,
    *,
    activo_id: uuid.UUID,
    articulo_id: uuid.UUID,
    notas: str | None = None,
) -> RepuestoCompatibilidad:
    if ActivoRepo(session).get(activo_id) is None:
        raise NoEncontrado("activo no encontrado")
    repo = RepuestoCompatibilidadRepo(session)
    existentes = repo.list_de_activo(activo_id)
    if any(r.articulo_id == articulo_id for r in existentes):
        raise Conflicto("ese repuesto ya está listado como compatible")
    return repo.add(
        RepuestoCompatibilidad(activo_id=activo_id, articulo_id=articulo_id, notas=notas)
    )


def quitar_compatible(session: Session, repuesto: RepuestoCompatibilidad) -> None:
    RepuestoCompatibilidadRepo(session).eliminar(repuesto)


def q_de_activo(session: Session, activo_id: uuid.UUID) -> list[RepuestoCompatibilidad]:
    return RepuestoCompatibilidadRepo(session).list_de_activo(activo_id)
