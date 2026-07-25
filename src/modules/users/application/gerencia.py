"""Administración de la matriz de aprobaciones (`regla_aprobacion`, en
`shared` — entidad transversal, no propiedad de `users`). Vive aquí porque
`users` ya es el hogar de facto de lo administrativo/transversal (mismo
criterio que `persona`)."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.users.application.errors import Conflicto, NoEncontrado
from src.shared.models import ReglaAprobacion
from src.shared.repositories import ReglaAprobacionRepo


def crear_regla(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    modulo: str,
    codigo: str,
    umbral: Decimal,
    permiso_requerido: str,
) -> ReglaAprobacion:
    repo = ReglaAprobacionRepo(session)
    if repo.get_vigente(empresa_id, modulo, codigo) is not None:
        raise Conflicto(f"ya existe una regla vigente para {modulo}.{codigo}")
    return repo.add(
        ReglaAprobacion(
            empresa_id=empresa_id,
            modulo=modulo,
            codigo=codigo,
            umbral=umbral,
            permiso_requerido=permiso_requerido,
        )
    )


def editar_regla(session: Session, regla_id: uuid.UUID, **campos) -> ReglaAprobacion:
    repo = ReglaAprobacionRepo(session)
    regla = repo.get(regla_id)
    if regla is None:
        raise NoEncontrado("regla de aprobación no encontrada")
    for campo in ("umbral", "permiso_requerido", "vigente"):
        if campo in campos and campos[campo] is not None:
            setattr(regla, campo, campos[campo])
    return regla


def listar_reglas(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[ReglaAprobacion]:
    return ReglaAprobacionRepo(session).list(empresa_id)
