"""Encuesta contestable **sin cuenta**: el cliente del restaurante no es
usuario del ERP.

Es la única superficie sin JWT del módulo, y por eso todo lo que devuelve
está recortado a lo mínimo: el nodo pendiente y nada del pedido. El token
del enlace es una credencial anónima —quien lo tenga contesta esa encuesta—
así que filtrar por él el cliente, la venta o el monto sería regalar datos
del pedido a cualquiera que reenvíe el link.

Sirve al canal `link` y al `pos` (la tablet del local abre la misma URL).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit
from src.modules.marketing.api import schemas
from src.modules.marketing.application import encuestas
from src.modules.marketing.application.errors import Conflicto
from src.modules.marketing.infrastructure.models import EncuestaSatisfaccion
from src.modules.marketing.infrastructure.repositories import EncuestaPlantillaRepo
from src.modules.users.api.deps import get_db

router = APIRouter(prefix="/marketing/publico", tags=["marketing"])

# Sin auth y con un token en la URL: el límite por IP es lo que impide
# probar tokens a fuerza bruta. Holgado para que una familia detrás del
# mismo NAT del local pueda contestar sin chocarse.
_limite = rate_limit("encuesta_publica", 60, 60)

MENSAJE_FINAL = "Encuesta completada."
MENSAJE_CERRADA = "Esta encuesta ya no admite respuestas."


@router.get("/encuestas/{token}", response_model=schemas.NodoPublicoOut)
def ver_nodo(
    token: str,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    return _nodo(session, encuestas.por_token(session, token))


@router.post("/encuestas/{token}/respuesta", response_model=schemas.NodoPublicoOut)
def responder(
    token: str,
    body: schemas.RespuestaPublicaIn,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    encuesta = encuestas.por_token(session, token)
    if encuesta.estado != "enviada":
        raise Conflicto(MENSAJE_CERRADA)
    encuestas.responder_nodo(session, encuesta, body.valor)
    session.commit()
    return _nodo(session, encuesta)


def _nodo(session: Session, encuesta: EncuestaSatisfaccion) -> dict:
    plantilla = (
        EncuestaPlantillaRepo(session).get(encuesta.plantilla_id)
        if encuesta.plantilla_id is not None
        else None
    )
    pregunta = encuestas.pregunta_actual(session, encuesta)
    terminada = pregunta is None or encuesta.estado != "enviada"
    return {
        "estado": encuesta.estado,
        "saludo": plantilla.saludo if plantilla is not None else "",
        "terminada": terminada,
        "mensaje": _mensaje(encuesta, plantilla, terminada),
        "pregunta": _pregunta(pregunta),
    }


def _mensaje(encuesta, plantilla, terminada: bool) -> str:
    if not terminada:
        return ""
    if encuesta.estado == "respondida":
        return plantilla.despedida if plantilla is not None else MENSAJE_FINAL
    return MENSAJE_CERRADA


def _pregunta(pregunta) -> dict | None:
    if pregunta is None:
        return None
    opciones = (
        [{"valor": "si", "etiqueta": "Sí"}, {"valor": "no", "etiqueta": "No"}]
        if pregunta.tipo == "si_no"
        else list(pregunta.opciones or [])
    )
    return {
        "codigo": pregunta.codigo,
        "texto": pregunta.texto,
        "tipo": pregunta.tipo,
        "opciones": opciones,
        "obligatoria": pregunta.obligatoria,
    }
