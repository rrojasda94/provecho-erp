"""Qué hacer con un mensaje que llega por WhatsApp.

El webhook no decide nada: solo verifica la firma y trae el mensaje. Acá
está la regla, que es corta y tiene un solo punto delicado —**el primer
mensaje del cliente no es una respuesta**—.

Meta no deja mandar preguntas fuera de la ventana de 24 h, así que la
encuesta se abre con una plantilla ("¿nos ayudas con 3 preguntas?"). El
cliente responde cualquier cosa ("sí", "ok", un emoji) y eso abre la
ventana: recién ahí sale la primera pregunta. Tratar ese "ok" como el
puntaje del pedido dejaría a media base con 0 estrellas por decir que sí.
"""

import logging

from sqlalchemy.orm import Session

from src.modules.marketing.application import encuestas as encuestas_uc
from src.modules.marketing.application import envios, tasks
from src.modules.marketing.application.errors import ReglaNegocio
from src.modules.marketing.infrastructure.repositories import EncuestaRepo
from src.shared.integrations.whatsapp import MensajeEntrante

log = logging.getLogger(__name__)


def procesar_mensaje(session: Session, mensaje: MensajeEntrante) -> bool:
    """Devuelve si el mensaje movió algo. `False` = no había encuesta abierta
    para ese número y se ignora (es lo que pasa con cualquiera que escriba al
    número del restaurante por otra cosa)."""
    encuesta = EncuestaRepo(session).abierta_de_telefono(mensaje.telefono)
    if encuesta is None:
        return False

    if not encuesta.conversacion_abierta:
        envios.abrir_conversacion(session, encuesta)
        session.commit()
        tasks.encolar(encuesta.id)
        return True

    # El id del botón es el valor exacto que mandó el ERP; el texto libre hay
    # que interpretarlo. Se prefiere el botón cuando vienen los dos.
    valor = mensaje.opcion_id or mensaje.texto
    try:
        encuestas_uc.responder_nodo(session, encuesta, valor)
    except ReglaNegocio as e:
        # Respuesta que el nodo no acepta: se repite la pregunta en vez de
        # cortar la conversación. El cliente no sabe que hay un guion.
        session.rollback()
        log.info("respuesta no válida en la encuesta %s: %s", encuesta.id, e)
        tasks.encolar(encuesta.id)
        return True

    session.commit()
    tasks.encolar(encuesta.id)
    return True
