"""Tareas en segundo plano de `rrhh`.

Cada tarea es una cáscara —abre la sesión, delega, hace commit—; la lógica
vive en su propio módulo (`avisos_asistencia.py`, `marcaciones.py`), que se
prueba sin broker.
"""

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.rrhh.application import avisos_asistencia, marcaciones

# Inyectable en tests, mismo patrón que `sales.application.tasks`.
session_factory = SessionLocal


@celery_app.task(name="rrhh.avisar_salidas_sin_marcar")
def avisar_salidas_sin_marcar() -> int:
    session = session_factory()
    try:
        avisadas = avisos_asistencia.barrer(session)
        session.commit()
        return len(avisadas)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="rrhh.purgar_fotos_de_marcacion")
def purgar_fotos_de_marcacion() -> int:
    session = session_factory()
    try:
        borradas = marcaciones.purgar_fotos_vencidas(
            session, settings.rrhh_marcaje_foto_retencion_dias
        )
        session.commit()
        return borradas
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
