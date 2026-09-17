"""Tareas en segundo plano de `supervision`: generar el día, cerrar
jornadas vencidas y purgar fotos viejas. Misma forma que `production.tasks`
y `rrhh.tasks`: la tarea abre su sesión, delega en el caso de uso y decide
si reintentar."""

from datetime import time, timedelta

from sqlalchemy import select, update

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.supervision.application import generacion, informes
from src.modules.supervision.infrastructure.models import TareaInstancia
from src.modules.users.infrastructure.models import Sucursal
from src.shared import fechas

# Inyectable (los tests la reemplazan), mismo patrón que `listeners`.
session_factory = SessionLocal


@celery_app.task(name="supervision.generar_tareas_del_dia")
def generar_tareas_del_dia() -> int:
    """Corre poco después de medianoche hora Perú: genera las instancias de
    hoy en todas las sucursales activas. `generar_instancias` es idempotente,
    así que un reintento o una generación manual el mismo día no duplica
    nada."""
    session = session_factory()
    try:
        generadas = generacion.generar_instancias(session, fechas.hoy())
        session.commit()
        return generadas
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="supervision.cerrar_jornadas_vencidas")
def cerrar_jornadas_vencidas() -> int:
    """Cada 15 minutos, mismo criterio que `production.generar_reportes_
    de_jornada_vencidos`: la hora de cierre es configurable
    (`supervision_hora_cierre_jornada`, hoy valor semilla y no por empresa —
    deuda declarada), así que no se puede programar con un solo `crontab`.
    """
    session = session_factory()
    cerradas = 0
    try:
        hoy = fechas.hoy()
        ahora = fechas.ahora()
        hora_cierre = time.fromisoformat(informes.hora_cierre_jornada())
        if ahora.time() < hora_cierre:
            return 0
        sucursales = session.scalars(
            select(Sucursal).where(Sucursal.estado == "activa", Sucursal.deleted_at.is_(None))
        )
        for sucursal in sucursales:
            informes.generar_informe(session, sucursal_id=sucursal.id, fecha=hoy, ahora=ahora)
            cerradas += 1
        session.commit()
        return cerradas
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="supervision.purgar_fotos")
def purgar_fotos() -> int:
    """Vacía la foto de tareas completadas hace más de
    `supervision_foto_retencion_dias`. Solo el binario: la fila y el resto
    de la evidencia (checklist, hora, quién) se quedan — mismo criterio que
    `rrhh.purgar_fotos_de_marcacion` y `delivery.purgar_evidencias`."""
    session = session_factory()
    try:
        limite = fechas.ahora() - timedelta(days=settings.supervision_foto_retencion_dias)
        resultado = session.execute(
            update(TareaInstancia)
            .where(
                TareaInstancia.completada_at < limite,
                TareaInstancia.foto.is_not(None),
            )
            .values(foto=None)
        )
        session.commit()
        return resultado.rowcount
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
