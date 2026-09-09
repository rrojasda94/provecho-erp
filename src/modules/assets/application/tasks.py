"""Tarea en segundo plano de `assets`: el barrido diario de vencimientos.

Misma forma que `inventory.tasks`: una cáscara que abre la sesión, delega en
el caso de uso y comitea. La lógica vive en `avisos.py` y se prueba sin
Celery ni broker.
"""

from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.assets.application import avisos

# Inyectable (los tests la reemplazan) — mismo patrón que
# `inventory.application.tasks` y `reports.application.listeners`. Sin esto,
# ejercitar el barrido en un test abriría la sesión de producción.
session_factory = SessionLocal


@celery_app.task(name="assets.barrer_vencimientos")
def barrer_vencimientos() -> dict:
    session = session_factory()
    try:
        publicados = avisos.barrer(session)
        session.commit()
        return publicados
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
