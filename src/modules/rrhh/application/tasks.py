"""Tareas en segundo plano de `rrhh`.

Una sola por ahora: el barrido de salidas sin marcar. La tarea es una
cáscara —abre la sesión, delega, hace commit—; la lógica vive en
`avisos_asistencia.py`, que se prueba sin broker.
"""

from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.rrhh.application import avisos_asistencia

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
