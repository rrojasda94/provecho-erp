"""Webhooks de pasarelas de pago hacia el sitio de marca (ADR-105).

Sin JWT, como cualquier webhook: lo que autentica la llamada es la **firma**
que verifica el adaptador de la pasarela (`Pasarela.verificar_webhook`), no una
sesión. Un cuerpo sin firma válida no toca la base.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit
from src.modules.storefront.application import pagos
from src.modules.users.api.deps import get_db
from src.shared.integrations.izipay import IzipayError, pasarela_activa

router = APIRouter(prefix="/storefront/webhooks", tags=["storefront"])

_limite = rate_limit("storefront_webhook_izipay", 120, 60)


def _procesar(session: Session, cuerpo: bytes, firma: str) -> dict:
    try:
        resultado = pasarela_activa().verificar_webhook(cuerpo, firma)
    except NotImplementedError as e:
        # Credenciales cargadas pero el adaptador real todavía sin terminar:
        # 501 y no un 500, para que se lea como "falta construirlo".
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(e)) from e
    except IzipayError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    pagos.registrar_resultado(
        session, id_externo=resultado.id_externo, aprobado=resultado.aprobado
    )
    return {"ok": True}


@router.post("/izipay")
async def webhook_izipay(
    request: Request,
    _=Depends(_limite),
    session: Session = Depends(get_db),
):
    """Recibe el resultado de un cobro. La firma viaja en `X-Izipay-Signature`
    (real) o `X-Izipay-Fake` (pasarela de prueba, solo fuera de producción). El
    cuerpo se lee crudo: la firma se calcula sobre los bytes exactos."""
    firma = request.headers.get("x-izipay-signature") or request.headers.get("x-izipay-fake") or ""
    cuerpo = await request.body()
    return await run_in_threadpool(_procesar, session, cuerpo, firma)
