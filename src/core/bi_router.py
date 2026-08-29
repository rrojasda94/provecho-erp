"""Guest tokens de Superset para embeber tableros en `/dashboard` (ADR-082
Fase D).

No confundir con `src/core/oauth/` (Fase B): aquello es el SSO humano
—Provecho como PROVEEDOR OAuth2 para que alguien entre a Superset—; esto es
Provecho como CLIENTE de la API de Superset, con su propia cuenta de
servicio, pidiendo un token de sesión acotado a un dashboard puntual.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.config.settings import settings
from src.modules.users.api.deps import require_permission
from src.modules.users.infrastructure.models import Usuario
from src.shared.integrations.superset.client import SupersetError, guest_token

router = APIRouter(prefix="/bi", tags=["bi"])

ACCEDER = "bi.acceder"


class GuestTokenOut(BaseModel):
    token: str


@router.get("/dashboards/{dashboard_id}/guest-token", response_model=GuestTokenOut)
def guest_token_de_dashboard(
    dashboard_id: str,
    usuario: Usuario = Depends(require_permission(ACCEDER)),
):
    # Whitelist explícita: aunque la fila ya la filtra la RLS del dataset
    # (Fase C), no cualquier UUID que alguien mande en la URL debe poder
    # pedirse un token — solo los tableros que de verdad se curaron.
    if dashboard_id not in settings.bi_dashboards_embebibles:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dashboard no habilitado para embeber")
    try:
        token = guest_token(
            dashboard_id,
            username=usuario.username,
            first_name=usuario.nombre_display or usuario.username,
            last_name="",
        )
    except SupersetError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    return {"token": token}
