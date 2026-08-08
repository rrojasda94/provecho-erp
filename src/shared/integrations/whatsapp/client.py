"""Cliente de la WhatsApp Cloud API (Meta).

Único punto del ERP que habla con Meta. El dominio nunca la llama: recibe
mensajes ya traducidos a `MensajeEntrante` y envía pidiendo `enviar_texto`
u `enviar_opciones`, sin saber que del otro lado hay botones o una lista.

Dos detalles del canal que condicionan el diseño y no son negociables:

- **Ventana de 24 h.** Fuera de una conversación abierta por el cliente,
  Meta solo acepta *plantillas* aprobadas. Por eso el primer mensaje de una
  encuesta sale por `enviar_plantilla` y las preguntas siguientes —ya dentro
  de la ventana que abrió su respuesta— por texto/interactivo normal.
- **Tope de opciones.** Los botones aceptan 3; más que eso obliga a una
  lista (hasta 10). `enviar_opciones` elige solo, porque quien arma la
  pregunta piensa en opciones, no en el widget de Meta.
"""

import hashlib
import hmac
import re
from dataclasses import dataclass

import httpx

from src.config.settings import settings


class WhatsAppError(RuntimeError):
    """Fallo de transporte o respuesta ilegible. Reintentable."""


class WhatsAppRechazo(RuntimeError):
    """Meta rechazó el mensaje (4xx): número inválido, plantilla no aprobada,
    fuera de la ventana de 24 h. **No** hereda de `WhatsAppError` a propósito:
    reenviar el mismo payload da el mismo rechazo, así que la tarea no
    reintenta y el fallo queda registrado en la fila."""


# Meta rechaza el mensaje entero si un botón se pasa; recortar es preferible
# a perder la pregunta (el texto completo va igual en el cuerpo).
MAX_BOTONES = 3
MAX_ITEMS_LISTA = 10
MAX_LARGO_BOTON = 20
MAX_LARGO_CUERPO = 1024

# Código de país por defecto al normalizar un teléfono local (Perú).
CODIGO_PAIS_DEFECTO = "51"
_LARGO_MOVIL_PE = 9


@dataclass(frozen=True)
class MensajeEntrante:
    """Un mensaje del cliente ya interpretado.

    `opcion_id` es el id que el ERP mandó en el botón/lista; viene vacío
    cuando el cliente escribió libremente en vez de tocar la opción — que
    es la mitad de los casos reales y por eso ambos campos conviven.
    """

    mensaje_id: str
    telefono: str
    texto: str
    opcion_id: str | None


def habilitado() -> bool:
    """Sin token o sin número emisor no hay envío posible. Se pregunta antes
    de encolar: una cola que acumula mensajes que nunca van a salir es peor
    que no encolarlos."""
    return bool(settings.whatsapp_token and settings.whatsapp_phone_number_id)


def normalizar_telefono(numero: str) -> str:
    """Deja solo dígitos y antepone el código de país si falta.

    El contacto del cliente se teclea en caja: llega como "987 654 321",
    "+51 987654321" o "(051) 987-654-321". Meta quiere E.164 sin `+`.
    Devuelve "" si no queda un número usable — el llamador decide qué hacer.
    """
    # Los ceros de la izquierda son prefijo de marcado (00 internacional, 0
    # troncal nacional), nunca parte del número: E.164 no empieza con cero.
    digitos = re.sub(r"\D", "", numero or "").lstrip("0")
    if not digitos:
        return ""
    if len(digitos) == _LARGO_MOVIL_PE:
        return CODIGO_PAIS_DEFECTO + digitos
    return digitos


def verificar_firma(cuerpo: bytes, cabecera: str | None) -> bool:
    """HMAC-SHA256 del cuerpo crudo contra `X-Hub-Signature-256`.

    El webhook es público: sin esto, cualquiera que conozca la URL puede
    contestar encuestas ajenas. Sin `WHATSAPP_APP_SECRET` configurado
    devuelve False —rechaza todo— en vez de aceptar todo: un webhook a
    medio configurar tiene que fallar cerrado.
    """
    secreto = settings.whatsapp_app_secret
    if not secreto or not cabecera or not cabecera.startswith("sha256="):
        return False
    esperado = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecera.removeprefix("sha256="))


def interpretar_webhook(cuerpo: dict) -> list[MensajeEntrante]:
    """Aplana el sobre de Meta (entry → changes → value → messages).

    Ignora en silencio lo que no sea un mensaje del usuario: los avisos de
    estado (`statuses`: enviado/entregado/leído) llegan por el mismo webhook
    y son mayoría. Un formato inesperado no levanta excepción — Meta
    reintenta el webhook ante cualquier error y quedaría en bucle.
    """
    mensajes: list[MensajeEntrante] = []
    for entrada in cuerpo.get("entry") or []:
        for cambio in entrada.get("changes") or []:
            for mensaje in (cambio.get("value") or {}).get("messages") or []:
                interpretado = _interpretar_mensaje(mensaje)
                if interpretado is not None:
                    mensajes.append(interpretado)
    return mensajes


def _interpretar_mensaje(mensaje: dict) -> MensajeEntrante | None:
    telefono = normalizar_telefono(mensaje.get("from") or "")
    mensaje_id = mensaje.get("id") or ""
    if not telefono or not mensaje_id:
        return None

    tipo = mensaje.get("type")
    if tipo == "text":
        texto = ((mensaje.get("text") or {}).get("body") or "").strip()
        return MensajeEntrante(mensaje_id, telefono, texto, None)
    if tipo == "interactive":
        interactivo = mensaje.get("interactive") or {}
        elegido = interactivo.get("button_reply") or interactivo.get("list_reply") or {}
        opcion = elegido.get("id")
        if not opcion:
            return None
        return MensajeEntrante(mensaje_id, telefono, elegido.get("title") or "", opcion)
    # Audio, imagen, ubicación, reacción: no son respuesta a una pregunta.
    return None


def _recortar(texto: str, largo: int) -> str:
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


class WhatsAppClient:
    def __init__(
        self,
        base_url: str | None = None,
        phone_number_id: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.whatsapp_base_url).rstrip("/")
        self.phone_number_id = phone_number_id or settings.whatsapp_phone_number_id
        self.token = token if token is not None else settings.whatsapp_token
        self.timeout = timeout or settings.whatsapp_timeout_segundos

    def enviar_texto(self, telefono: str, texto: str) -> str:
        return self._enviar(
            {
                "messaging_product": "whatsapp",
                "to": telefono,
                "type": "text",
                "text": {"body": _recortar(texto, MAX_LARGO_CUERPO)},
            }
        )

    def enviar_opciones(
        self, telefono: str, texto: str, opciones: list[tuple[str, str]]
    ) -> str:
        """Pregunta cerrada. Hasta 3 opciones van como botones; de 4 a 10,
        como lista desplegable. Sin opciones, cae a texto plano — así el
        llamador no tiene que preguntar de qué tipo es la pregunta."""
        if not opciones:
            return self.enviar_texto(telefono, texto)
        if len(opciones) <= MAX_BOTONES:
            interactivo = self._botones(opciones)
        else:
            interactivo = self._lista(opciones[:MAX_ITEMS_LISTA])
        interactivo["body"] = {"text": _recortar(texto, MAX_LARGO_CUERPO)}
        return self._enviar(
            {
                "messaging_product": "whatsapp",
                "to": telefono,
                "type": "interactive",
                "interactive": interactivo,
            }
        )

    def enviar_plantilla(
        self, telefono: str, nombre: str, idioma: str, parametros: list[str]
    ) -> str:
        """Mensaje de plantilla aprobada: el único que Meta acepta fuera de
        la ventana de 24 h, y por eso el que abre toda encuesta."""
        componentes = []
        if parametros:
            componentes.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in parametros],
                }
            )
        return self._enviar(
            {
                "messaging_product": "whatsapp",
                "to": telefono,
                "type": "template",
                "template": {
                    "name": nombre,
                    "language": {"code": idioma},
                    "components": componentes,
                },
            }
        )

    @staticmethod
    def _botones(opciones: list[tuple[str, str]]) -> dict:
        return {
            "type": "button",
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": valor, "title": _recortar(etiqueta, MAX_LARGO_BOTON)},
                    }
                    for valor, etiqueta in opciones
                ]
            },
        }

    @staticmethod
    def _lista(opciones: list[tuple[str, str]]) -> dict:
        return {
            "type": "list",
            "action": {
                "button": "Responder",
                "sections": [
                    {
                        "title": "Opciones",
                        "rows": [
                            {"id": valor, "title": _recortar(etiqueta, MAX_LARGO_BOTON)}
                            for valor, etiqueta in opciones
                        ],
                    }
                ],
            },
        }

    def _enviar(self, payload: dict) -> str:
        """Devuelve el id del mensaje en Meta (sirve para cruzar el acuse).

        Un 4xx es un dato mal armado y **no** se reintenta: reenviar el mismo
        payload da el mismo 400 y consume la cola. Transporte caído y 5xx sí
        levantan `WhatsAppError`, que es lo que la tarea reintenta.
        """
        if not habilitado():
            raise WhatsAppError("WHATSAPP_TOKEN/WHATSAPP_PHONE_NUMBER_ID no configurados")
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        try:
            respuesta = httpx.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise WhatsAppError(f"WhatsApp no responde: {e}") from e
        if respuesta.status_code >= 500:
            raise WhatsAppError(f"WhatsApp devolvió {respuesta.status_code}")
        try:
            cuerpo = respuesta.json()
        except ValueError as e:
            raise WhatsAppError(f"Respuesta ilegible de WhatsApp: {e}") from e
        if respuesta.status_code >= 400:
            detalle = (cuerpo.get("error") or {}).get("message") or respuesta.text
            raise WhatsAppRechazo(f"WhatsApp rechazó el mensaje: {detalle}")
        mensajes = cuerpo.get("messages") or [{}]
        return mensajes[0].get("id") or ""
