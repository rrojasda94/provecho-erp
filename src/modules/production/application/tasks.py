"""Tareas en segundo plano de `production`: el barrido de cierre de
jornada (RN-DOC-010).

Misma forma que `inventory.tasks`/`sales.tasks`: la tarea es una cáscara
que abre la sesión, delega en el caso de uso y decide si reintentar. La
lógica vive en `reportes_jornada.py` y se prueba sin broker ni red.
"""

from sqlalchemy import select

from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.production.application import reportes_jornada
from src.modules.users.infrastructure.models import Almacen
from src.shared import fechas

# Inyectable (los tests la reemplazan), mismo patrón que `listeners`.
session_factory = SessionLocal


@celery_app.task(name="production.generar_reportes_de_jornada_vencidos")
def generar_reportes_de_jornada_vencidos() -> int:
    """Corre cada 15 minutos y no una vez al día porque `hora_cierre_
    jornada` es configurable por empresa (`parametro_empresa`, no un
    horario único de servidor): un barrido diario a hora fija cerraría
    tarde a la empresa que configuró un cierre temprano.

    Idempotente por `(almacen_id, jornada)` — `generar_reporte_jornada`
    no vuelve a tocar un reporte ya visado, así que solaparse con la
    generación manual (`POST /reportes-jornada/generar`) no duplica nada.
    """
    session = session_factory()
    generados = 0
    try:
        hoy = fechas.hoy()
        ahora = fechas.ahora().time()
        almacenes = session.scalars(
            select(Almacen).where(
                Almacen.tipo == "produccion", Almacen.deleted_at.is_(None)
            )
        )
        for almacen in almacenes:
            hora_cierre = reportes_jornada.hora_cierre_jornada_de(session, almacen.empresa_id)
            if ahora < hora_cierre:
                continue
            reportes_jornada.generar_reporte_jornada(session, almacen_id=almacen.id, jornada=hoy)
            generados += 1
        session.commit()
        return generados
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
