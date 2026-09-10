"""Router público de seguimiento del cliente (RN-DLV-008, ADR-098).

Es la única superficie de `delivery` sin JWT: el cliente que sigue su
pedido no es usuario del ERP. El token del enlace es la credencial —el
límite por IP es lo que impide probar tokens a fuerza bruta— mismo
criterio que `marketing/api/publico_routers.py`.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit
from src.modules.delivery.api import schemas
from src.modules.delivery.application import seguimiento
from src.modules.users.api.deps import get_db

router = APIRouter(prefix="/delivery/publico", tags=["delivery"])

# Holgado a propósito, como el de la encuesta pública: la pantalla del
# cliente refresca cada 10 s y una familia entera puede mirar el mismo
# pedido desde el mismo NAT.
_limite = rate_limit("seguimiento_publico", 120, 60)


@router.get("/seguimiento/{token}", response_model=schemas.SeguimientoOut)
def ver_seguimiento(
    token: str,
    response: Response,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    resultado = seguimiento.por_token(session, token)
    # 404 uniforme para token inexistente, vencido o de una entrega
    # cancelada (RN-DLV-008): las tres respuestas tienen que ser
    # indistinguibles, o quien reenvía el link confirma que ese token
    # existió alguna vez.
    if resultado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no encontrado")
    # Nunca cacheado — ni por el navegador ni por un proxy intermedio: es
    # la posición en vivo de otra persona.
    response.headers["Cache-Control"] = "no-store"
    return resultado
