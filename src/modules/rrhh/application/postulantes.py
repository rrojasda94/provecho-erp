"""Casos de uso de `postulante`: crear (exige consentimiento previo,
RN-PER-004) y cambiar estado del proceso de selección."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import NoEncontrado, ReglaNegocio
from src.modules.rrhh.infrastructure.models import Postulante
from src.modules.rrhh.infrastructure.repositories import PostulanteRepo
from src.modules.users.infrastructure.models import Persona

_ESTADOS = {"en_proceso", "rechazado", "contratado"}


def crear_postulante(
    session: Session,
    *,
    persona_id: uuid.UUID,
    puesto_postulado: str,
    fecha_postulacion: date,
    consentimiento_datos: bool,
    consentimiento_fecha: date | None = None,
    plazo_conservacion_declarado: date | None = None,
    cv_archivo_id: uuid.UUID | None = None,
) -> Postulante:
    if not consentimiento_datos:
        raise ReglaNegocio(
            "datos de postulante requieren consentimiento previo e informado (RN-PER-004)"
        )
    if session.get(Persona, persona_id) is None:
        raise NoEncontrado(f"persona {persona_id} no encontrada")

    return PostulanteRepo(session).add(
        Postulante(
            persona_id=persona_id,
            puesto_postulado=puesto_postulado,
            fecha_postulacion=fecha_postulacion,
            consentimiento_datos=consentimiento_datos,
            consentimiento_fecha=consentimiento_fecha or fecha_postulacion,
            plazo_conservacion_declarado=plazo_conservacion_declarado,
            cv_archivo_id=cv_archivo_id,
        )
    )


def listar_postulantes(session: Session, estado: str | None = None) -> list[Postulante]:
    return PostulanteRepo(session).list(estado)


def cambiar_estado_postulante(
    session: Session, postulante_id: uuid.UUID, *, estado: str
) -> Postulante:
    if estado not in _ESTADOS:
        raise ReglaNegocio(f"estado inválido: {estado}")
    postulante = PostulanteRepo(session).get(postulante_id)
    if postulante is None:
        raise NoEncontrado("postulante no encontrado")
    postulante.estado = estado
    return postulante
