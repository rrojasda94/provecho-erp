"""Adaptador de la WhatsApp Cloud API: lo que no se puede probar contra Meta.

Tres cosas que fallan en silencio si nadie las mira: un teléfono tecleado en
caja que no queda en E.164 (Meta lo rechaza y la encuesta nunca sale), una
firma de webhook que se acepta cuando no debería (cualquiera contesta
encuestas ajenas), y un sobre de Meta que se interpreta mal (los avisos de
"entregado" contados como respuestas del cliente).
"""

import hashlib
import hmac

import httpx
import pytest

from src.config.settings import settings
from src.shared.integrations import whatsapp
from src.shared.integrations.whatsapp import client as wa_client

SECRETO = "secreto-de-prueba"


@pytest.fixture()
def configurado(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_token", "token")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "999")
    monkeypatch.setattr(settings, "whatsapp_app_secret", SECRETO)
    monkeypatch.setattr(settings, "whatsapp_base_url", "https://graph.example/v21.0")


@pytest.mark.parametrize(
    ("tecleado", "esperado"),
    [
        ("999888777", "51999888777"),
        ("+51 987 654 321", "51987654321"),
        ("(051) 987-654-321", "51987654321"),
        ("0051987654321", "51987654321"),
        ("", ""),
        ("sin numero", ""),
    ],
)
def test_el_telefono_tecleado_en_caja_queda_en_e164(tecleado, esperado):
    assert whatsapp.normalizar_telefono(tecleado) == esperado


def test_la_firma_del_webhook_falla_cerrada(monkeypatch):
    """Sin secreto configurado rechaza todo. Un webhook a medio configurar
    tiene que fallar cerrado: aceptar todo es dejar la puerta abierta."""
    cuerpo = b'{"entry":[]}'
    monkeypatch.setattr(settings, "whatsapp_app_secret", "")
    firma = "sha256=" + hmac.new(b"", cuerpo, hashlib.sha256).hexdigest()
    assert whatsapp.verificar_firma(cuerpo, firma) is False

    monkeypatch.setattr(settings, "whatsapp_app_secret", SECRETO)
    buena = "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
    assert whatsapp.verificar_firma(cuerpo, buena) is True
    assert whatsapp.verificar_firma(cuerpo, "sha256=otra") is False
    assert whatsapp.verificar_firma(cuerpo, None) is False
    # Un byte distinto invalida la firma: por eso el webhook usa el crudo.
    assert whatsapp.verificar_firma(cuerpo + b" ", buena) is False


def test_solo_los_mensajes_del_cliente_se_interpretan():
    """Los avisos de estado (enviado/entregado/leído) llegan por el mismo
    webhook y son mayoría: contarlos como respuestas duplicaría todo."""
    payload = {
        "entry": [
            {
                "changes": [
                    {"value": {"statuses": [{"id": "wamid.1", "status": "delivered"}]}},
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.2",
                                    "from": "51999888777",
                                    "type": "text",
                                    "text": {"body": " 5 "},
                                },
                                {
                                    "id": "wamid.3",
                                    "from": "51999888777",
                                    "type": "interactive",
                                    "interactive": {
                                        "button_reply": {"id": "si", "title": "Sí"}
                                    },
                                },
                                {"id": "wamid.4", "from": "51999888777", "type": "audio"},
                            ]
                        }
                    },
                ]
            }
        ]
    }
    mensajes = whatsapp.interpretar_webhook(payload)
    assert [m.mensaje_id for m in mensajes] == ["wamid.2", "wamid.3"]
    assert mensajes[0].texto == "5" and mensajes[0].opcion_id is None
    assert mensajes[1].opcion_id == "si"


def test_un_sobre_inesperado_no_levanta_excepcion():
    """Meta reintenta el webhook ante cualquier error: una excepción acá
    deja el endpoint en bucle hasta que Meta desactiva la suscripción."""
    assert whatsapp.interpretar_webhook({}) == []
    assert whatsapp.interpretar_webhook({"entry": [{"changes": [{}]}]}) == []


def _capturar(monkeypatch, respuesta: httpx.Response) -> list[dict]:
    enviados: list[dict] = []

    def _post(url, json=None, headers=None, timeout=None):
        enviados.append({"url": url, "json": json})
        return respuesta

    monkeypatch.setattr(wa_client.httpx, "post", _post)
    return enviados


def _ok() -> httpx.Response:
    return httpx.Response(
        200,
        json={"messages": [{"id": "wamid.OK"}]},
        request=httpx.Request("POST", "https://graph.example"),
    )


def test_hasta_tres_opciones_van_como_botones_y_mas_como_lista(configurado, monkeypatch):
    """Meta rechaza el mensaje entero con 4 botones. Elegir el widget es del
    adaptador: quien arma la pregunta piensa en opciones, no en widgets."""
    enviados = _capturar(monkeypatch, _ok())
    cliente = whatsapp.WhatsAppClient()

    cliente.enviar_opciones("51999888777", "¿Qué tal?", [("si", "Sí"), ("no", "No")])
    assert enviados[-1]["json"]["interactive"]["type"] == "button"

    cliente.enviar_opciones(
        "51999888777", "Del 1 al 5", [(str(n), f"Nivel {n}") for n in range(1, 6)]
    )
    assert enviados[-1]["json"]["interactive"]["type"] == "list"


def test_sin_opciones_cae_a_texto_plano(configurado, monkeypatch):
    enviados = _capturar(monkeypatch, _ok())
    whatsapp.WhatsAppClient().enviar_opciones("51999888777", "¿Algo más?", [])
    assert enviados[-1]["json"]["type"] == "text"


def test_un_rechazo_de_meta_no_es_reintentable(configurado, monkeypatch):
    """Reenviar el mismo payload da el mismo 400 y consume la cola; solo el
    transporte caído merece reintento."""
    _capturar(
        monkeypatch,
        httpx.Response(
            400,
            json={"error": {"message": "Template name does not exist"}},
            request=httpx.Request("POST", "https://graph.example"),
        ),
    )
    with pytest.raises(whatsapp.WhatsAppRechazo):
        whatsapp.WhatsAppClient().enviar_texto("51999888777", "hola")


def test_un_500_si_es_reintentable(configurado, monkeypatch):
    _capturar(
        monkeypatch,
        httpx.Response(503, request=httpx.Request("POST", "https://graph.example")),
    )
    with pytest.raises(whatsapp.WhatsAppError):
        whatsapp.WhatsAppClient().enviar_texto("51999888777", "hola")


def test_sin_token_no_se_intenta_la_llamada(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_token", "")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "")
    assert whatsapp.habilitado() is False
    with pytest.raises(whatsapp.WhatsAppError):
        whatsapp.WhatsAppClient().enviar_texto("51999888777", "hola")
