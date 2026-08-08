"""Tareas en segundo plano de `marketing`: envío de la encuesta y barrido de
vigencia.

La tarea es una cáscara — abre la sesión, delega en el caso de uso y decide
si reintentar. La lógica vive en `envios.py`/`encuestas.py`, que se prueban
sin broker ni red.
"""

import logging
import uuid

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.marketing.application import encuestas as encuestas_uc
from src.modules.marketing.application import envios
from src.modules.marketing.infrastructure.repositories import EncuestaRepo
from src.shared.integrations import whatsapp

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan), mismo patrón que `listeners`.
session_factory = SessionLocal

# Reintentos espaciados: 1, 2, 4... minutos. Un rechazo de Meta no reintenta
# (no es fallo de transporte, el dato está mal) — `envios.despachar` ya lo
# absorbe y lo deja escrito en la fila.
REINTENTOS_MAXIMOS = 4
ESPERA_BASE_SEGUNDOS = 60


@celery_app.task(
    bind=True,
    name="marketing.despachar_encuesta",
    autoretry_for=(whatsapp.WhatsAppError,),
    retry_backoff=ESPERA_BASE_SEGUNDOS,
    retry_kwargs={"max_retries": REINTENTOS_MAXIMOS},
)
def despachar_encuesta(self, encuesta_id: str) -> str:
    session = session_factory()
    try:
        return _despachar(session, uuid.UUID(encuesta_id))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="marketing.barrer_encuestas_vencidas")
def barrer_encuestas_vencidas() -> int:
    """Expiración automática. Sin esto, una encuesta sin respuesta queda
    `enviada` para siempre y el porcentaje de respuesta nunca cierra."""
    session = session_factory()
    try:
        cantidad = encuestas_uc.expirar_vencidas(session)
        session.commit()
        return cantidad
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def encolar(encuesta_id: uuid.UUID) -> None:
    """Encola el envío. Se llama DESPUÉS del commit (el listener de
    `marketing.encuesta_enviada` corre post-commit, ADR-016).

    Sin WhatsApp configurado no hace nada: una cola que acumula mensajes que
    nunca van a salir es peor que no encolarlos. En un hub de sucursal
    tampoco — no corre Celery y la mensajería sale siempre de la nube
    (ADR-009).

    Si el broker no responde, manda en línea antes que perder el mensaje: el
    llamador ya está fuera del request del usuario, así que el costo de la
    llamada HTTP no se lo paga nadie mirando una pantalla.
    """
    if settings.es_hub or not whatsapp.habilitado():
        return
    try:
        despachar_encuesta.apply_async(args=[str(encuesta_id)], retry=False)
    except Exception:
        log.warning("Broker no disponible: encuesta %s se envía en línea", encuesta_id)
        _enviar_en_linea(encuesta_id)


def _enviar_en_linea(encuesta_id: uuid.UUID) -> None:
    session = session_factory()
    try:
        _despachar(session, encuesta_id)
    except Exception:
        session.rollback()
        log.exception("fallo enviando la encuesta %s", encuesta_id)
    finally:
        session.close()


def _despachar(session, encuesta_id: uuid.UUID) -> str:
    encuesta = EncuestaRepo(session).get(encuesta_id)
    if encuesta is None:
        return "inexistente"
    accion = envios.despachar(session, encuesta)
    session.commit()
    return accion
