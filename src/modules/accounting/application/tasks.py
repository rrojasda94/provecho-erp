"""Tarea en segundo plano de `accounting`: la depreciación mensual.

Misma forma que `assets.application.tasks`: una cáscara que abre la
sesión, delega en el caso de uso y comitea. La lógica vive en
`depreciacion.py` y se prueba sin Celery ni broker.
"""

from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.accounting.application import depreciacion

# Inyectable (los tests la reemplazan) — mismo patrón que
# `assets.application.tasks`. Sin esto, ejercitar el barrido en un test
# abriría la sesión de producción.
session_factory = SessionLocal


@celery_app.task(name="accounting.correr_depreciacion_mensual")
def correr_depreciacion_mensual() -> dict:
    session = session_factory()
    try:
        resultado = depreciacion.correr_depreciacion_mensual(session)
        session.commit()
        return resultado
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
