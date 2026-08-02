"""Casos de uso de `socio`: participación societaria, referenciada en
aprobaciones (RN-GRP-006, RN-MAR-004). No implica `trabajador` ni `usuario`."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import NoEncontrado, ReglaNegocio
from src.modules.rrhh.infrastructure.models import Socio
from src.modules.rrhh.infrastructure.repositories import SocioRepo
from src.modules.users.infrastructure.models import Empresa, Grupo, Persona


def crear_socio(
    session: Session,
    *,
    porcentaje_participacion: Decimal,
    grupo_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    persona_id: uuid.UUID | None = None,
    razon_social: str | None = None,
    ruc: str | None = None,
) -> Socio:
    if grupo_id is None and empresa_id is None:
        raise ReglaNegocio("socio requiere grupo_id o empresa_id")
    if persona_id is None and not (razon_social and ruc):
        raise ReglaNegocio("socio requiere persona_id o razon_social+ruc")
    if grupo_id is not None and session.get(Grupo, grupo_id) is None:
        raise NoEncontrado(f"grupo {grupo_id} no encontrado")
    if empresa_id is not None and session.get(Empresa, empresa_id) is None:
        raise NoEncontrado(f"empresa {empresa_id} no encontrada")
    if persona_id is not None and session.get(Persona, persona_id) is None:
        raise NoEncontrado(f"persona {persona_id} no encontrada")

    return SocioRepo(session).add(
        Socio(
            grupo_id=grupo_id,
            empresa_id=empresa_id,
            persona_id=persona_id,
            razon_social=razon_social,
            ruc=ruc,
            porcentaje_participacion=porcentaje_participacion,
        )
    )


def listar_socios(session: Session, empresa_id: uuid.UUID | None = None) -> list[Socio]:
    return SocioRepo(session).list(empresa_id)
