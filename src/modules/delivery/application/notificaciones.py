"""Aviso al cliente por WhatsApp, uno por hito (ADR-098).

Mismo patrón que `marketing.application.envios`: el único punto de
`delivery` que sabe que del otro lado hay una API de Meta, y lo sabe a
través del adaptador (`src/shared/integrations/whatsapp`) — el caso de uso
que registra la entrega nunca lo importa, lo dispara por evento
(`listeners.py` → `tasks.encolar_aviso`).

Un rechazo de Meta (número inexistente, plantilla no aprobada) queda en
`entrega.aviso_error` y **no** levanta: reintentar el mismo payload da el
mismo rechazo. Un fallo de transporte sí propaga, para que la cola
reintente (`tasks.despachar_notificacion`).
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.delivery.application.seguimiento import url_publica
from src.modules.delivery.infrastructure.models import Entrega, Repartidor
from src.modules.rrhh.application.queries_publicas import cuenta_de_trabajador
from src.modules.sales.application.queries_publicas import (
    contacto_de_cliente,
    venta_para_reparto,
)
from src.modules.users.infrastructure.models import Sucursal
from src.shared.integrations import whatsapp

log = logging.getLogger(__name__)

EN_CAMINO = "en_camino"
ENTREGADO = "entregado"
FALLIDA = "fallida"
HITOS = (EN_CAMINO, ENTREGADO, FALLIDA)

SIN_ENVIO = "sin_envio"
ENVIADO = "enviado"
RECHAZADO = "rechazado"
SIN_TELEFONO = "sin_telefono"

# Inyectable: los tests la reemplazan por un doble sin red, igual que
# `marketing.application.envios.cliente_factory`.
cliente_factory = whatsapp.WhatsAppClient

# Texto llano para la plantilla `entrega_fallida` — presentación, no una
# regla de negocio (esas viven en `domain/rules.py::MOTIVOS_FALLO`). Mismo
# criterio que el `ETIQUETA_MOTIVO` del frontend (`lib/delivery.ts`).
MOTIVO_LEGIBLE = {
    "cliente_ausente": "no encontramos a nadie en la dirección",
    "direccion_errada": "la dirección no correspondía",
    "rechazo": "el pedido fue rechazado",
    "no_contesta": "no contestó el timbre ni el teléfono",
    "otro": "no se pudo completar la entrega",
}


def despachar(session: Session, entrega_id, hito: str) -> str:
    """Manda el aviso del hito indicado y devuelve qué hizo."""
    entrega = session.get(Entrega, entrega_id)
    if entrega is None:
        return SIN_ENVIO
    if not whatsapp.habilitado():
        log.info("WhatsApp no configurado: entrega %s sin aviso (%s)", entrega_id, hito)
        return SIN_ENVIO

    venta = venta_para_reparto(session, entrega.venta_id)
    contacto = contacto_de_cliente(session, venta["cliente_id"]) if venta else None
    telefono = (contacto or {}).get("telefono") if contacto else None
    if not telefono:
        entrega.aviso_error = SIN_TELEFONO
        session.flush()
        return SIN_TELEFONO

    cliente_nombre = (contacto or {}).get("nombre") or "Hola"
    cliente = cliente_factory()
    try:
        if hito == EN_CAMINO:
            mensaje_id = _avisar_en_camino(session, cliente, entrega, telefono, cliente_nombre)
        elif hito == ENTREGADO:
            mensaje_id = _avisar_entregado(cliente, entrega, telefono, cliente_nombre, venta)
        else:
            mensaje_id = _avisar_fallida(session, cliente, entrega, telefono, cliente_nombre)
    except whatsapp.WhatsAppRechazo as e:
        entrega.aviso_error = str(e)[:255]
        session.flush()
        log.warning("WhatsApp rechazó el aviso de la entrega %s (%s): %s", entrega_id, hito, e)
        return RECHAZADO

    _marcar_enviado(entrega, hito)
    entrega.aviso_error = None
    session.flush()
    log.info("Aviso %s de la entrega %s enviado: %s", hito, entrega_id, mensaje_id)
    return ENVIADO


def _marcar_enviado(entrega: Entrega, hito: str) -> None:
    ahora = datetime.now(UTC)
    if hito == EN_CAMINO:
        entrega.aviso_en_camino_at = ahora
    else:
        # `entregado` y `fallida` comparten una sola columna de resultado:
        # una entrega solo tiene un desenlace, nunca los dos.
        entrega.aviso_resultado_at = ahora


def _avisar_en_camino(
    session: Session, cliente, entrega: Entrega, telefono, cliente_nombre
) -> str:
    repartidor_nombre = _nombre_repartidor(session, entrega.repartidor_id)
    parametros = [
        cliente_nombre,
        repartidor_nombre or "tu repartidor",
        _eta_minutos(entrega),
        _enlace(entrega),
    ]
    return cliente.enviar_plantilla(
        telefono,
        settings.whatsapp_plantilla_en_camino,
        settings.whatsapp_plantilla_idioma,
        parametros,
    )


def _avisar_entregado(
    cliente, entrega: Entrega, telefono, cliente_nombre, venta: dict | None
) -> str:
    numero_orden = (venta or {}).get("numero_orden") or ""
    return cliente.enviar_plantilla(
        telefono,
        settings.whatsapp_plantilla_entregado,
        settings.whatsapp_plantilla_idioma,
        [cliente_nombre, str(numero_orden)],
    )


def _avisar_fallida(session: Session, cliente, entrega: Entrega, telefono, cliente_nombre) -> str:
    motivo_legible = MOTIVO_LEGIBLE.get(entrega.motivo_fallo or "", MOTIVO_LEGIBLE["otro"])
    contacto_sucursal = _nombre_sucursal(session, entrega.sucursal_id)
    return cliente.enviar_plantilla(
        telefono,
        settings.whatsapp_plantilla_entrega_fallida,
        settings.whatsapp_plantilla_idioma,
        [cliente_nombre, motivo_legible, contacto_sucursal],
    )


def _nombre_repartidor(session: Session, repartidor_id) -> str | None:
    if repartidor_id is None:
        return None
    repartidor = session.get(Repartidor, repartidor_id)
    if repartidor is None:
        return None
    cuenta = cuenta_de_trabajador(session, repartidor.trabajador_id)
    if not cuenta or not cuenta.get("nombre"):
        return None
    # Solo el primer nombre — mismo criterio que el enlace público
    # (RN-DLV-008): no le manda al cliente más identificación de la
    # necesaria.
    return cuenta["nombre"].split()[0]


def _nombre_sucursal(session: Session, sucursal_id) -> str:
    sucursal = session.get(Sucursal, sucursal_id)
    return sucursal.nombre if sucursal is not None else "el local"


def _enlace(entrega: Entrega) -> str:
    if not entrega.token_publico:
        return ""
    return url_publica(entrega.token_publico)


def _sin_zona(valor: datetime) -> datetime:
    """Mismo problema que `seguimiento._sin_zona`: SQLite devuelve
    `entrega.eta_at` sin tzinfo tras recargar la fila, y restarle un
    `datetime` con zona revienta. Postgres conserva la zona, así que acá es
    un no-op."""
    return valor.replace(tzinfo=None) if valor.tzinfo else valor


def _eta_minutos(entrega: Entrega) -> str:
    if entrega.eta_at is None:
        return "unos minutos"
    restante = _sin_zona(entrega.eta_at) - _sin_zona(datetime.now(UTC))
    minutos = max(1, round(restante.total_seconds() / 60))
    return str(minutos)
