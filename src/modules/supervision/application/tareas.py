"""Ejecución de una tarea: marcar ítems del checklist, adjuntar foto y
completar. `completar` es el único acto que cambia `estado` — marcar un
ítem o subir la foto no lo hace, así que el trabajador puede ir y volver
sin perder lo ya hecho."""

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.modules.supervision.application import fotos
from src.modules.supervision.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.supervision.domain import rules
from src.modules.supervision.infrastructure.models import TareaInstancia
from src.modules.supervision.infrastructure.repositories import TareaInstanciaRepo
from src.shared import auditoria


def q_mis_tareas(session: Session, usuario_id: uuid.UUID, fecha: date):
    return TareaInstanciaRepo(session).q_asignadas_a(usuario_id, fecha)


def q_tareas_de_sucursal(session: Session, sucursal_id: uuid.UUID, fecha: date):
    return TareaInstanciaRepo(session).q_de_sucursal(sucursal_id, fecha)


def _exigir_instancia(session: Session, instancia_id: uuid.UUID) -> TareaInstancia:
    instancia = TareaInstanciaRepo(session).get(instancia_id)
    if instancia is None:
        raise NoEncontrado("tarea no encontrada")
    return instancia


def _exigir_es_el_asignado(instancia: TareaInstancia, actor_id: uuid.UUID) -> None:
    if not rules.puede_ejecutar(instancia.asignado_a, actor_id):
        raise ReglaNegocio("solo el trabajador asignado puede ejecutar esta tarea")


def marcar_item(
    session: Session, instancia_id: uuid.UUID, indice: int, *, hecho: bool, actor_id: uuid.UUID
) -> TareaInstancia:
    instancia = _exigir_instancia(session, instancia_id)
    _exigir_es_el_asignado(instancia, actor_id)
    if instancia.estado != "pendiente":
        raise Conflicto("la tarea ya no está pendiente")
    checklist = list(instancia.checklist)
    if indice < 0 or indice >= len(checklist):
        raise NoEncontrado("ítem de checklist no encontrado")
    checklist[indice] = {**checklist[indice], "hecho": hecho}
    instancia.checklist = checklist
    session.flush()
    return instancia


def adjuntar_foto(
    session: Session, instancia_id: uuid.UUID, contenido: bytes, *, actor_id: uuid.UUID
) -> TareaInstancia:
    instancia = _exigir_instancia(session, instancia_id)
    _exigir_es_el_asignado(instancia, actor_id)
    if instancia.estado != "pendiente":
        raise Conflicto("la tarea ya no está pendiente")
    if len(contenido) > fotos.TAMANO_MAXIMO_ENTRADA_BYTES:
        raise ReglaNegocio(
            f"la foto supera el máximo de {fotos.TAMANO_MAXIMO_ENTRADA_BYTES // (1024 * 1024)} MB"
        )
    comprimida, tomada_at = fotos.procesar(contenido)
    instancia.foto = comprimida
    instancia.foto_tomada_at = tomada_at
    session.flush()
    return instancia


def completar(
    session: Session,
    instancia_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    ahora: datetime,
    tolerancia_minutos: int,
    observacion: str | None = None,
) -> TareaInstancia:
    instancia = _exigir_instancia(session, instancia_id)
    _exigir_es_el_asignado(instancia, actor_id)
    if instancia.estado != "pendiente":
        raise Conflicto("la tarea ya no está pendiente")
    if not rules.puede_completar(
        checklist=instancia.checklist,
        requiere_foto=instancia.requiere_foto,
        tiene_foto=instancia.foto is not None,
    ):
        raise ReglaNegocio("checklist incompleto o falta la foto que la tarea exige")
    instancia.foto_valida = rules.foto_es_de_ahora(
        instancia.foto_tomada_at, ahora, tolerancia_minutos
    )
    instancia.estado = "completada"
    # La hora de finalización es la del servidor, no la que mande el
    # cliente: es justo lo que valida contra el EXIF de la foto.
    instancia.completada_at = ahora
    instancia.completada_por = actor_id
    if observacion is not None:
        instancia.observacion = observacion
    session.flush()
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="tarea_instancia",
        entidad_id=instancia.id,
        accion="completar",
        datos_despues={"foto_valida": instancia.foto_valida},
        sucursal_id=instancia.sucursal_id,
    )
    return instancia
