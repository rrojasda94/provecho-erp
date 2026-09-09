"""Tareas en segundo plano de `delivery`: barridos periódicos de datos
operativos con retención propia y el aviso al cliente por WhatsApp
(ADR-098).

Las de purga son una cáscara — abren su sesión, delegan y no reintentan:
son barridos de limpieza, no un envío que le importe a alguien si tarda un
ciclo más. `despachar_notificacion` sí reintenta (fallo de transporte,
`whatsapp.WhatsAppError`) — la lógica del envío vive en `notificaciones.py`,
que se prueba sin broker ni red.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.core.database import SessionLocal
from src.modules.delivery.application import notificaciones
from src.modules.delivery.infrastructure.models import Entrega
from src.modules.delivery.infrastructure.repositories import PosicionRepo
from src.shared.integrations import whatsapp

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan), mismo patrón que `listeners`: sin
# esto un barrido ejercitado en un test abre la sesión de producción.
session_factory = SessionLocal

#: Estados de `entrega` que ya no van a cambiar — solo de una de estas se
#: purga la evidencia, nunca de una entrega todavía en curso.
_ESTADOS_RESUELTOS = ("entregada", "fallida", "cancelada")

# Reintentos espaciados: 1, 2, 4... minutos. Un rechazo de Meta no
# reintenta (no es fallo de transporte, el dato está mal) —
# `notificaciones.despachar` ya lo absorbe y lo deja escrito en la fila.
REINTENTOS_MAXIMOS = 4
ESPERA_BASE_SEGUNDOS = 60


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


@celery_app.task(
    bind=True,
    name="delivery.notificar_cliente",
    autoretry_for=(whatsapp.WhatsAppError,),
    retry_backoff=ESPERA_BASE_SEGUNDOS,
    retry_kwargs={"max_retries": REINTENTOS_MAXIMOS},
)
def despachar_notificacion(self, entrega_id: str, hito: str) -> str:
    session = session_factory()
    try:
        return _despachar(session, uuid.UUID(entrega_id), hito)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def encolar_aviso(entrega_id: uuid.UUID, hito: str) -> None:
    """Encola el aviso del hito. Se llama DESPUÉS del commit (los listeners
    de `delivery.ruta_iniciada`/`entrega_registrada`/`entrega_fallida`
    corren post-commit, ADR-016).

    Sin WhatsApp configurado no hace nada: una cola que acumula mensajes
    que nunca van a salir es peor que no encolarlos. En un hub de sucursal
    tampoco — no corre Celery y la mensajería sale siempre de la nube
    (ADR-009).

    Si el broker no responde, manda en línea antes que perder el aviso: el
    llamador ya está fuera del request del usuario, así que el costo de la
    llamada HTTP no se lo paga nadie mirando una pantalla.
    """
    if settings.es_hub or not whatsapp.habilitado():
        return
    try:
        despachar_notificacion.apply_async(args=[str(entrega_id), hito], retry=False)
    except Exception:
        log.warning(
            "Broker no disponible: aviso %s de la entrega %s se envía en línea",
            hito,
            entrega_id,
        )
        _enviar_en_linea(entrega_id, hito)


def _enviar_en_linea(entrega_id: uuid.UUID, hito: str) -> None:
    session = session_factory()
    try:
        _despachar(session, entrega_id, hito)
    except Exception:
        session.rollback()
        log.exception("fallo enviando el aviso %s de la entrega %s", hito, entrega_id)
    finally:
        session.close()


def _despachar(session, entrega_id: uuid.UUID, hito: str) -> str:
    accion = notificaciones.despachar(session, entrega_id, hito)
    session.commit()
    return accion
