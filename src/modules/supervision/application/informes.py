"""Informe diario de supervisión: cierra la jornada de una sucursal.

Idempotente por `(sucursal_id, fecha)`: correr el barrido de cierre dos
veces, o generar a mano después de que ya corrió, no duplica el informe —
lo recalcula mientras el día siga siendo hoy o esté recién cerrado.
"""

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.supervision.application.errors import NoEncontrado
from src.modules.supervision.domain import rules
from src.modules.supervision.infrastructure.models import InformeDiario
from src.modules.supervision.infrastructure.repositories import (
    InformeDiarioRepo,
    TareaInstanciaRepo,
)


def q_informes(session: Session, sucursal_id: uuid.UUID | None = None):
    return InformeDiarioRepo(session).q_list(sucursal_id)


def generar_informe(
    session: Session, *, sucursal_id: uuid.UUID, fecha: date, ahora: datetime
) -> InformeDiario:
    tarea_repo = TareaInstanciaRepo(session)
    # Toda tarea que siga pendiente al cerrar la jornada se da por vencida
    # (RN-SUP-007): no hay ventana de gracia después del cierre.
    for pendiente in tarea_repo.pendientes_de_sucursal(sucursal_id, fecha):
        if rules.vencida_al_cierre(pendiente.estado):
            pendiente.estado = "vencida"

    tareas = tarea_repo.de_sucursal(sucursal_id, fecha)
    completadas = sum(1 for t in tareas if t.estado == "completada")
    vencidas = sum(1 for t in tareas if t.estado == "vencida")
    fotos_invalidas = sum(1 for t in tareas if t.foto_valida is False)

    repo = InformeDiarioRepo(session)
    informe = repo.get_de(sucursal_id, fecha)
    if informe is None:
        # `generado_at` va en el constructor: `repo.add` hace `flush`
        # de inmediato y la columna es NOT NULL sin default.
        informe = repo.add(
            InformeDiario(sucursal_id=sucursal_id, fecha=fecha, generado_at=ahora)
        )
    informe.total = len(tareas)
    informe.completadas = completadas
    informe.vencidas = vencidas
    informe.fotos_invalidas = fotos_invalidas
    informe.generado_at = ahora
    session.flush()

    event_bus.publish(
        "supervision.informe_diario_generado",
        {
            "informe_id": str(informe.id),
            "sucursal_id": str(sucursal_id),
            "fecha": fecha.isoformat(),
            "total": informe.total,
            "completadas": informe.completadas,
            "vencidas": informe.vencidas,
            "fotos_invalidas": informe.fotos_invalidas,
        },
        session=session,
    )
    return informe


def hora_cierre_jornada() -> str:
    return settings.supervision_hora_cierre_jornada


def obtener_informe(session: Session, informe_id: uuid.UUID) -> InformeDiario:
    informe = InformeDiarioRepo(session).get(informe_id)
    if informe is None:
        raise NoEncontrado("informe no encontrado")
    return informe
