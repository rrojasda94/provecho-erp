"""Barridos periódicos de `delivery`: purga de datos operativos con
retención propia (ADR-098).

Cada tarea es una cáscara — abre su sesión, delega y decide si hace falta
reintentar. Ninguna de las dos tiene reintento: son barridos de limpieza,
no un envío que le importe a alguien si tarda un ciclo más.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.delivery.infrastructure.models import Entrega
from src.modules.delivery.infrastructure.repositories import PosicionRepo

# Inyectable (los tests la reemplazan), mismo patrón que `listeners`: sin
# esto un barrido ejercitado en un test abre la sesión de producción.
session_factory = SessionLocal

#: Estados de `entrega` que ya no van a cambiar — solo de una de estas se
#: purga la evidencia, nunca de una entrega todavía en curso.
_ESTADOS_RESUELTOS = ("entregada", "fallida", "cancelada")


@celery_app.task(name="delivery.purgar_posiciones")
def purgar_posiciones() -> int:
    """Borra el breadcrumb de GPS más viejo que
    `delivery_posiciones_retencion_dias`. Es rastro operativo para
    auditoría de una salida reciente, no un libro contable — no hace
    falta guardarlo para siempre."""
    session = session_factory()
    try:
        limite = datetime.now(UTC) - timedelta(days=settings.delivery_posiciones_retencion_dias)
        borradas = PosicionRepo(session).borrar_anteriores_a(limite)
        session.commit()
        return borradas
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="delivery.purgar_evidencias")
def purgar_evidencias() -> int:
    """Vacía la foto de evidencia de entregas ya resueltas hace más de
    `delivery_evidencia_retencion_dias`. Solo el binario: la fila y el
    resto de la entrega (motivo, fecha, quién) se quedan — mismo criterio
    que `rrhh.purgar_fotos_de_marcacion`."""
    session = session_factory()
    try:
        limite = datetime.now(UTC) - timedelta(days=settings.delivery_evidencia_retencion_dias)
        resultado = session.execute(
            update(Entrega)
            .where(
                Entrega.estado.in_(_ESTADOS_RESUELTOS),
                Entrega.updated_at < limite,
                Entrega.evidencia_foto.is_not(None),
            )
            .values(evidencia_foto=None)
        )
        session.commit()
        return resultado.rowcount
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
