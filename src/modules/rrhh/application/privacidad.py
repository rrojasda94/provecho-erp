"""Derechos ARCO sobre `postulante` (Ley 29733, ADR-011).

`postulante` no vive en `persona` —postular no mete a nadie en la fuente
única de la empresa— así que `POST /personas/{id}/anonimizar` no lo alcanza
y necesita su equivalente. Mismo criterio que allá: **anonimización, no
`DELETE`**. Acá nada referencia la fila y un borrado sería posible, pero se
llevaría `motivo_descarte` y `canal_origen` — la evidencia de por qué se
descartó a alguien (defensa ante un reclamo de discriminación, Ley 26772) y
la constancia de que la solicitud de cancelación existió.

Lo que sobrevive es deliberadamente no identificable: puesto, canal, fechas
y el motivo del descarte. Por eso el motivo se redacta como criterio ("sin
disponibilidad para turno noche"), nunca con datos personales.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import Conflicto, NoEncontrado
from src.modules.rrhh.infrastructure.models import Postulante
from src.modules.rrhh.infrastructure.repositories import PostulanteRepo
from src.modules.users.infrastructure.repositories import AuditLogRepo

MARCADOR_ANONIMO = "ANONIMIZADO"
CAMPOS_ANONIMIZADOS = ("nombres", "apellidos", "telefono", "email", "respuestas")


def anonimizar_postulante(
    session: Session,
    postulante_id: uuid.UUID,
    *,
    motivo: str,
    solicitado_por: uuid.UUID | None,
) -> Postulante:
    postulante = PostulanteRepo(session).get(postulante_id)
    if postulante is None:
        raise NoEncontrado("postulante no encontrado")
    if postulante.anonimizado_at is not None:
        raise Conflicto("el postulante ya fue anonimizado")
    if postulante.trabajador_id is not None:
        # Ya es trabajador: sus datos viven en `persona` y están bajo
        # retención laboral. Su ARCO se ejerce allá, no acá.
        raise Conflicto(
            "el postulante fue contratado; su cancelación se ejerce sobre la persona"
        )

    postulante.nombres = MARCADOR_ANONIMO
    postulante.apellidos = MARCADOR_ANONIMO
    postulante.telefono = None
    postulante.email = None
    postulante.respuestas = None
    postulante.anonimizado_at = datetime.now(UTC)

    # Igual que en `users`: se registra QUÉ se borró y por qué, nunca el
    # valor — guardarlo en el audit_log dejaría la PII accesible ahí para
    # siempre y vaciaría de sentido la anonimización.
    AuditLogRepo(session).registrar(
        usuario_id=solicitado_por,
        entidad="postulante",
        entidad_id=postulante.id,
        accion="anonimizar",
        datos_despues={"campos_anonimizados": list(CAMPOS_ANONIMIZADOS), "motivo": motivo},
    )
    session.flush()
    return postulante


def postulantes_vencidos(session: Session, hasta: date) -> list[Postulante]:
    """Fichas cuyo plazo de conservación declarado ya venció y que no
    derivaron en contratación."""
    return list(
        session.scalars(
            select(Postulante).where(
                Postulante.anonimizado_at.is_(None),
                Postulante.trabajador_id.is_(None),
                Postulante.plazo_conservacion_declarado.is_not(None),
                Postulante.plazo_conservacion_declarado < hasta,
            )
        )
    )


def purgar_postulantes_vencidos(session: Session, hasta: date) -> int:
    """Aplica el plazo declarado en el aviso de privacidad. Sin esto el
    plazo es una promesa que el sistema no cumple, y el incumplimiento
    crece con cada postulación."""
    vencidos = postulantes_vencidos(session, hasta)
    for postulante in vencidos:
        anonimizar_postulante(
            session,
            postulante.id,
            motivo="plazo de conservación vencido (RN-PER-004)",
            solicitado_por=None,
        )
    return len(vencidos)
