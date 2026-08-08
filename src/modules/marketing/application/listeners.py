"""Listeners de marketing: los de `sales` y **los propios**.

De `sales` escucha `venta_confirmada` para la atribución lead→venta. Los
otros seis son de marketing sobre marketing, y eso no es un rodeo: los
eventos que el módulo publicaba (`campana_lanzada`, `lead_generado`) no
tenían consumidor y se perdían. El acumulado de campaña
(`application/metricas.py`) es ese consumidor, y el envío real del WhatsApp
cuelga de `encuesta_enviada` — que gracias a ADR-016 se despacha recién al
commitear, así que el worker encuentra la fila que va a leer.

Atribución lead→venta: solo cuando **no hay ambigüedad** —el cliente tiene
exactamente un lead abierto en una campaña en curso—. Con dos o más, adivinar
cuál campaña se lleva el crédito falsearía la medición de conversión; esos
casos quedan para `POST /marketing/leads/{id}/atribucion`.

Nunca bloquean la operación que los disparó: cualquier fallo se loguea,
mismo criterio que `inventory`/`accounting`.
"""

import logging
import uuid

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.marketing.application import metricas
from src.modules.marketing.infrastructure.repositories import LeadRepo

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan), mismo patrón que los otros módulos.
session_factory = SessionLocal


def on_venta_confirmada(payload: dict) -> None:
    cliente_id = payload.get("cliente_id")
    if not cliente_id:
        return
    try:
        with session_factory() as session:
            abiertos = LeadRepo(session).sin_atribuir_de_cliente(uuid.UUID(cliente_id))
            if len(abiertos) != 1:
                if abiertos:
                    log.info(
                        "venta %s: %s leads abiertos del cliente, atribución manual",
                        payload.get("venta_id"),
                        len(abiertos),
                    )
                return
            lead = abiertos[0]
            lead.venta_id = uuid.UUID(payload["venta_id"])
            # El contador de conversiones lo mueve `on_lead_atribuido`, no
            # esta función: atribución manual y automática tienen que sumar
            # por el mismo camino o una de las dos se olvida de sumar.
            event_bus.publish(
                "marketing.lead_atribuido",
                {
                    "lead_id": str(lead.id),
                    "campana_id": str(lead.campana_id),
                    "venta_id": payload["venta_id"],
                    "automatica": True,
                },
                session=session,
            )
            session.commit()
    except Exception:
        log.exception("fallo atribuyendo lead de la venta %s", payload.get("venta_id"))


def on_campana_lanzada(payload: dict) -> None:
    _acumular(
        payload,
        lambda session: metricas.registrar_lanzamiento(
            session, uuid.UUID(payload["campana_id"])
        ),
    )


def on_lead_generado(payload: dict) -> None:
    _acumular(
        payload,
        lambda session: metricas.sumar_lead(session, uuid.UUID(payload["campana_id"])),
    )


def on_lead_atribuido(payload: dict) -> None:
    _acumular(
        payload,
        lambda session: metricas.sumar_conversion(
            session, uuid.UUID(payload["campana_id"])
        ),
    )


def on_pieza_publicada(payload: dict) -> None:
    campana_id = payload.get("campana_id")
    if not campana_id:
        # Contenido de marca siempre-verde: no cuelga de ninguna campaña.
        return
    _acumular(payload, lambda session: metricas.sumar_pieza(session, uuid.UUID(campana_id)))


def on_encuesta_enviada(payload: dict) -> None:
    """Acumula y **manda el mensaje**. El envío se encola aparte de la
    transacción del acumulado: que Meta esté caído no puede dejar la métrica
    sin escribir, ni al revés."""
    _acumular(
        payload,
        lambda session: metricas.sumar_encuesta_enviada(
            session, uuid.UUID(payload["venta_id"])
        ),
    )
    try:
        from src.modules.marketing.application import tasks

        tasks.encolar(uuid.UUID(payload["encuesta_id"]))
    except Exception:
        log.exception("fallo encolando el envío de la encuesta %s", payload.get("encuesta_id"))


def on_encuesta_respondida(payload: dict) -> None:
    _acumular(
        payload,
        lambda session: metricas.sumar_encuesta_respondida(
            session, uuid.UUID(payload["venta_id"]), payload.get("puntaje")
        ),
    )


def _acumular(payload: dict, accion) -> None:
    try:
        with session_factory() as session:
            accion(session)
            session.commit()
    except Exception:
        log.exception("fallo acumulando métricas de marketing (%s)", payload)


_registrado = False

_SUSCRIPCIONES = (
    ("sales.venta_confirmada", on_venta_confirmada),
    ("marketing.campana_lanzada", on_campana_lanzada),
    ("marketing.lead_generado", on_lead_generado),
    ("marketing.lead_atribuido", on_lead_atribuido),
    ("marketing.pieza_publicada", on_pieza_publicada),
    ("marketing.encuesta_enviada", on_encuesta_enviada),
    ("marketing.encuesta_respondida", on_encuesta_respondida),
)


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    for evento, handler in _SUSCRIPCIONES:
        event_bus.subscribe(evento, handler)
