"""Webhook de WhatsApp: por acá entra lo que el cliente contesta.

Es público por definición —lo llama Meta, no un usuario del ERP— así que la
autenticación es la **firma HMAC** del cuerpo crudo contra
`WHATSAPP_APP_SECRET`. Por eso el cuerpo se recibe como `bytes` y se parsea
a mano: cualquier reserialización cambia el JSON y la firma deja de validar.

Dos reglas que impone Meta y que explican la forma del endpoint:

- **Siempre 200.** Un error devuelto hace que Meta reintente el webhook en
  bucle y termine desactivando la suscripción. Lo que falla se registra y se
  contesta 200 igual.
- **Handshake GET.** Al dar de alta la URL, Meta pide un `hub.challenge` y
  espera el eco en texto plano.
"""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.rate_limit import rate_limit
from src.modules.marketing.application import conversacion
from src.modules.users.api.deps import get_db
from src.shared.integrations import whatsapp

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["marketing"])

# Meta manda ráfagas; el límite corta un flood contra el endpoint público
# sin estorbar la operación normal.
_limite = rate_limit("whatsapp_webhook", 600, 60)


async def cuerpo_crudo(request: Request) -> bytes:
    """Los bytes tal como llegaron. Declararlo como `bytes = Body(...)` haría
    que FastAPI parsee el JSON y lo reserialice, y la firma —que se calcula
    sobre el crudo— dejaría de validar."""
    return await request.body()


@router.get("/whatsapp", response_class=PlainTextResponse)
def verificar_webhook(
    modo: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    desafio: str = Query("", alias="hub.challenge"),
    _=Depends(_limite),
):
    """Handshake de alta de la URL en Meta."""
    if modo != "subscribe" or not settings.whatsapp_verify_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "verificación no válida")
    if token != settings.whatsapp_verify_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "verificación no válida")
    return desafio


@router.post("/whatsapp")
def recibir_webhook(
    cuerpo: bytes = Depends(cuerpo_crudo),
    firma: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    if not whatsapp.verificar_firma(cuerpo, firma):
        # 403 y no 200: acá sí conviene que el emisor se entere, porque un
        # cuerpo sin firma válida no viene de Meta.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "firma no válida")

    try:
        payload = json.loads(cuerpo or b"{}")
    except ValueError:
        log.warning("Webhook de WhatsApp con cuerpo ilegible")
        return {"procesados": 0}

    procesados = 0
    for mensaje in whatsapp.interpretar_webhook(payload):
        try:
            if conversacion.procesar_mensaje(session, mensaje):
                procesados += 1
        except Exception:
            session.rollback()
            log.exception("fallo procesando el mensaje %s", mensaje.mensaje_id)
    return {"procesados": procesados}
