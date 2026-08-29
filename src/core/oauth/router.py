"""OAuth2 (Authorization Code) para el SSO del BI (Superset, ADR-082 Fase B).

Tres endpoints, dos formas de autenticarse:

- `POST /oauth/codigo`: el único que ve una sesión de Provecho (JWT +
  `bi.acceder`, ADR-082/RN-BI-004). No es el navegador el que lo llama: la
  cookie de sesión (`provecho_token`) es httpOnly y host-only de
  `staging.majambo.com.pe` y nunca llega a la API en otro subdominio (ADR-004
  no la amplía a propósito). Quien la lee y llama acá es el route handler
  `frontend/app/oauth/authorize/route.ts`, del lado del servidor de Next.js,
  que es donde esa cookie sí existe.
- `/token` y `/userinfo`: servidor-a-servidor. Los llama Superset con
  `client_id`/`client_secret` (RFC 6749 §4.1.3) o el access token que
  `/token` acaba de emitir — nunca el navegador, nunca un JWT de Provecho.

Los errores de protocolo se traducen al mismo sobre `{"detail": "..."}` que
usa el resto del ERP (`core/error_handlers.py`) y no al `{"error": ...}` de
RFC 6749 §5.2: Superset/Authlib solo necesitan el status code para fallar el
intercambio, y un segundo formato de error sería una excepción más que
mantener por una interoperabilidad que nadie pidió.
"""

from fastapi import APIRouter, Depends, Form, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.oauth import servicio
from src.core.oauth.servicio import OAuthError
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo

router = APIRouter(prefix="/oauth", tags=["oauth"])

ACCEDER = "bi.acceder"


def _error(e: OAuthError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, f"{e.codigo}: {e.descripcion}")


class CodigoIn(BaseModel):
    client_id: str
    redirect_uri: str


class CodigoOut(BaseModel):
    codigo: str


@router.post("/codigo", response_model=CodigoOut)
def emitir_codigo(
    body: CodigoIn,
    usuario: Usuario = Depends(require_permission(ACCEDER)),
):
    try:
        codigo = servicio.emitir_codigo(usuario.id, body.client_id, body.redirect_uri)
    except OAuthError as e:
        raise _error(e) from e
    return {"codigo": codigo}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/token", response_model=TokenOut)
def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
):
    try:
        access_token, expira_en = servicio.canjear_codigo(
            grant_type=grant_type,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
        )
    except OAuthError as e:
        raise _error(e) from e
    return {"access_token": access_token, "token_type": "bearer", "expires_in": expira_en}


class UserInfoOut(BaseModel):
    sub: str
    preferred_username: str
    email: str | None
    name: str
    roles: list[str]


@router.get("/userinfo", response_model=UserInfoOut)
def userinfo(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el access token")
    access_token = authorization[len("Bearer ") :].strip()

    usuario_id = servicio.usuario_id_del_token(access_token)
    if usuario_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Access token inválido o vencido")

    repo = UsuarioRepo(session)
    usuario = repo.get(usuario_id)
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inválido")

    return {
        "sub": str(usuario.id),
        "preferred_username": usuario.username,
        "email": usuario.email,
        "name": usuario.nombre_display or usuario.username,
        "roles": repo.rol_nombres(usuario.id),
    }
