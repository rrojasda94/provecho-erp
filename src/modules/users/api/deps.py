"""Dependencias FastAPI: sesión (Unit of Work por request), usuario actual,
contexto de tenant (ADR-004) y verificación de permisos (deny por defecto)."""

import uuid
from collections.abc import Iterator

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.tenant import Tenant
from src.modules.users.domain import rules
from src.modules.users.infrastructure.models import Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo
from src.modules.users.infrastructure.security import decode_access_token

_bearer = HTTPBearer(auto_error=True)


def get_db() -> Iterator[Session]:
    """La sesión es la Unit of Work; los endpoints hacen commit explícito.
    Rollback automático ante excepción no controlada."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_claims(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """Claims validados del access token. FastAPI cachea la dependencia, así
    que el token se decodifica una sola vez por request."""
    try:
        return decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado"
        ) from None


def get_current_user(
    claims: dict = Depends(get_claims),
    session: Session = Depends(get_db),
) -> Usuario:
    usuario = UsuarioRepo(session).get(uuid.UUID(claims["sub"]))
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inválido")
    return usuario


def get_tenant(claims: dict = Depends(get_claims)) -> Tenant:
    """Contexto de tenant del request (ADR-004). Único origen válido del
    `empresa_id`/`sucursal_id` de una operación — el body no manda."""
    return Tenant.from_claims(claims)


def require_permission(codigo: str):
    """Factory de dependencia: exige el permiso `codigo` (o comodín `*`)."""

    def _dep(
        usuario: Usuario = Depends(get_current_user),
        session: Session = Depends(get_db),
    ) -> Usuario:
        codigos = UsuarioRepo(session).permiso_codigos(usuario.id)
        if not rules.permite(codigos, codigo):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado")
        return usuario

    return _dep


def tiene_permiso(session: Session, usuario: Usuario, codigo: str) -> bool:
    """Chequeo sin bloquear, para respuestas que muestran más o menos según
    el rol (ej. el conteo "a ciegas" oculta el stock esperado, RN-INV-005).
    `require_permission` sigue siendo la vía para negar el acceso."""
    return rules.permite(UsuarioRepo(session).permiso_codigos(usuario.id), codigo)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
