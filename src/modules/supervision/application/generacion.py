"""Generación diaria de tareas: por cada sucursal activa y cada plantilla
que le aplica, si `rules.toca_hoy` fabrica la `TareaInstancia` del día.

Idempotente por `(plantilla_id, fecha)` (índice único parcial en el modelo):
correr el barrido dos veces el mismo día, o generar a mano después de que ya
corrió, no duplica nada.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.supervision.application.errors import NoEncontrado, ReglaNegocio
from src.modules.supervision.domain import rules
from src.modules.supervision.infrastructure.models import TareaInstancia, TareaPlantilla
from src.modules.supervision.infrastructure.repositories import (
    TareaInstanciaRepo,
    TareaPlantillaRepo,
)
from src.modules.users.infrastructure.models import Sucursal


def _instancia_de(plantilla: TareaPlantilla, sucursal_id: uuid.UUID, hoy: date) -> TareaInstancia:
    return TareaInstancia(
        plantilla_id=plantilla.id,
        sucursal_id=sucursal_id,
        fecha=hoy,
        momento=plantilla.momento,
        orden=plantilla.orden,
        nombre=plantilla.nombre,
        categoria_id=plantilla.categoria_id,
        requiere_foto=plantilla.requiere_foto,
        checklist=[{"texto": texto, "hecho": False} for texto in plantilla.checklist],
        asignado_a=plantilla.asignado_a,
    )


def generar_instancias_de_sucursal(session: Session, sucursal: Sucursal, hoy: date) -> int:
    plantilla_repo = TareaPlantillaRepo(session)
    instancia_repo = TareaInstanciaRepo(session)
    generadas = 0
    for plantilla in plantilla_repo.activas_de_sucursal(sucursal.id, sucursal.marca_id):
        if not rules.toca_hoy(
            frecuencia=plantilla.frecuencia,
            fecha_inicio=plantilla.fecha_inicio,
            hoy=hoy,
            dia_semana=plantilla.dia_semana,
            dia_mes=plantilla.dia_mes,
        ):
            continue
        if instancia_repo.existe_de_plantilla(plantilla.id, sucursal.id, hoy):
            continue
        instancia_repo.add(_instancia_de(plantilla, sucursal.id, hoy))
        generadas += 1
    return generadas


def generar_instancias(session: Session, hoy: date, empresa_id: uuid.UUID | None = None) -> int:
    """Recorre las sucursales activas (de una empresa, o todas) y genera lo
    que toque en cada una. Lo usa tanto el barrido de Celery como
    `POST /supervision/tareas/generar`."""
    q = select(Sucursal).where(Sucursal.estado == "activa", Sucursal.deleted_at.is_(None))
    if empresa_id is not None:
        q = q.where(Sucursal.empresa_id == empresa_id)
    total = 0
    for sucursal in session.scalars(q):
        total += generar_instancias_de_sucursal(session, sucursal, hoy)
    return total


def crear_tarea_manual(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    fecha: date,
    momento: str,
    nombre: str,
    categoria_id: uuid.UUID,
    orden: int = 1,
    requiere_foto: bool = False,
    checklist: list[str] | None = None,
    asignado_a: uuid.UUID | None = None,
) -> TareaInstancia:
    """Un imprevisto del día que no amerita una plantilla permanente."""
    if momento not in rules.MOMENTOS:
        raise ReglaNegocio(f"momento inválido: {momento}")
    instancia = TareaInstancia(
        plantilla_id=None,
        sucursal_id=sucursal_id,
        fecha=fecha,
        momento=momento,
        orden=orden,
        nombre=nombre,
        categoria_id=categoria_id,
        requiere_foto=requiere_foto,
        checklist=[{"texto": texto, "hecho": False} for texto in (checklist or [])],
        asignado_a=asignado_a,
    )
    return TareaInstanciaRepo(session).add(instancia)


def asignar(session: Session, instancia_id: uuid.UUID, *, usuario_id: uuid.UUID) -> TareaInstancia:
    instancia = TareaInstanciaRepo(session).get(instancia_id)
    if instancia is None:
        raise NoEncontrado("tarea no encontrada")
    instancia.asignado_a = usuario_id
    session.flush()
    return instancia
