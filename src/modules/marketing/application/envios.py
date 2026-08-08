"""Envío real de la encuesta por su canal.

Traduce un nodo del guion a un mensaje de WhatsApp y lo manda. Es el único
punto de `marketing` que sabe que del otro lado hay una API de Meta, y lo
sabe a través del adaptador (`src/shared/integrations/whatsapp`): el caso de
uso de la encuesta nunca lo importa.

Secuencia real de una encuesta por WhatsApp:

1. `plantilla` — Meta no acepta nada más fuera de la ventana de 24 h, así
   que el primer mensaje es la plantilla aprobada, con el nombre del cliente
   y el enlace por si prefiere el formulario web.
2. El cliente contesta cualquier cosa → se abre la ventana → se le manda la
   **primera pregunta** (su mensaje no se interpreta como respuesta: todavía
   no se le preguntó nada).
3. De ahí en adelante, cada respuesta avanza un nodo y dispara la siguiente
   pregunta, hasta que el guion corta y sale la despedida.

`pos` y `link` no mandan nada: la tablet del local y la URL pública muestran
el nodo directamente.
"""

import logging

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.marketing.application import encuestas as encuestas_uc
from src.modules.marketing.infrastructure.models import (
    EncuestaPregunta,
    EncuestaSatisfaccion,
)
from src.modules.marketing.infrastructure.repositories import EncuestaPlantillaRepo
from src.modules.sales.application.queries_publicas import contacto_de_cliente
from src.shared.integrations import whatsapp

log = logging.getLogger(__name__)

DESPEDIDA_POR_DEFECTO = "¡Gracias por responder!"
SIN_ENLACE = "responde por aquí"

# Inyectable: los tests la reemplazan por un doble sin red, igual que
# `listeners.session_factory`.
cliente_factory = whatsapp.WhatsAppClient

SIN_ENVIO = "sin_envio"
APERTURA = "plantilla"
PREGUNTA = "pregunta"
CIERRE = "despedida"
RECHAZADO = "rechazado"


def despachar(session: Session, encuesta: EncuestaSatisfaccion) -> str:
    """Manda lo que corresponda ahora mismo y devuelve qué hizo.

    Un rechazo de Meta (número inexistente, plantilla no aprobada) queda en
    `error_envio` y **no** levanta: reintentar el mismo payload da el mismo
    rechazo, y lo que hace falta es que alguien vea por qué esa encuesta
    nunca llegó. Un fallo de transporte sí propaga, para que la cola
    reintente.
    """
    if encuesta.canal not in encuestas_uc.CANALES_CON_DESTINO or not encuesta.destino:
        return SIN_ENVIO
    if not whatsapp.habilitado():
        log.info("WhatsApp no configurado: encuesta %s sin envío", encuesta.id)
        return SIN_ENVIO

    cliente = cliente_factory()
    try:
        if not encuesta.conversacion_abierta:
            accion, mensaje_id = APERTURA, _abrir(session, cliente, encuesta)
        elif encuesta.estado == "enviada" and encuesta.pregunta_actual_id is not None:
            pregunta = encuestas_uc.pregunta_actual(session, encuesta)
            accion, mensaje_id = PREGUNTA, _preguntar(cliente, encuesta, pregunta)
        else:
            accion, mensaje_id = CIERRE, _despedir(session, cliente, encuesta)
    except whatsapp.WhatsAppRechazo as e:
        encuesta.error_envio = str(e)[:255]
        session.flush()
        log.warning("WhatsApp rechazó la encuesta %s: %s", encuesta.id, e)
        return RECHAZADO

    encuesta.mensaje_externo_id = mensaje_id or None
    encuesta.error_envio = None
    session.flush()
    return accion


def abrir_conversacion(session: Session, encuesta: EncuestaSatisfaccion) -> None:
    """El cliente escribió por primera vez: se abre la ventana de 24 h y a
    partir de acá sus mensajes sí son respuestas."""
    encuesta.conversacion_abierta = True
    session.flush()


def texto_de_pregunta(pregunta: EncuestaPregunta) -> str:
    """La pregunta como la lee el cliente. Las opciones se repiten en el
    cuerpo aunque vayan como botones: quien contesta desde un WhatsApp viejo
    —o desde el enlace web— no ve el widget, solo el texto."""
    opciones = _opciones(pregunta)
    if not opciones:
        return pregunta.texto
    listado = "\n".join(f"{valor}) {etiqueta}" for valor, etiqueta in opciones)
    return f"{pregunta.texto}\n{listado}"


def _abrir(session: Session, cliente, encuesta: EncuestaSatisfaccion) -> str:
    """La plantilla aprobada lleva **siempre dos parámetros** (nombre y
    enlace). Meta rechaza el mensaje si falta uno o si viene vacío, así que
    sin `MARKETING_URL_PUBLICA` configurada el segundo cae a un texto: la
    encuesta se puede contestar igual respondiendo el chat."""
    contacto = contacto_de_cliente(session, encuesta.cliente_id) or {}
    nombre = (contacto.get("nombre") or "").strip() or "Hola"
    enlace = encuestas_uc.url_publica(encuesta) or SIN_ENLACE
    return cliente.enviar_plantilla(
        encuesta.destino,
        settings.whatsapp_plantilla_encuesta,
        settings.whatsapp_plantilla_idioma,
        [nombre, enlace],
    )


def _preguntar(cliente, encuesta: EncuestaSatisfaccion, pregunta) -> str:
    if pregunta is None:
        return ""
    return cliente.enviar_opciones(
        encuesta.destino, texto_de_pregunta(pregunta), _opciones(pregunta)
    )


def _despedir(session: Session, cliente, encuesta: EncuestaSatisfaccion) -> str:
    plantilla = (
        EncuestaPlantillaRepo(session).get(encuesta.plantilla_id)
        if encuesta.plantilla_id is not None
        else None
    )
    despedida = plantilla.despedida if plantilla is not None else DESPEDIDA_POR_DEFECTO
    return cliente.enviar_texto(encuesta.destino, despedida)


def _opciones(pregunta: EncuestaPregunta) -> list[tuple[str, str]]:
    if pregunta.tipo == "si_no":
        return [("si", "Sí"), ("no", "No")]
    return [
        (o["valor"], o.get("etiqueta", o["valor"])) for o in (pregunta.opciones or [])
    ]
