"""Dependencias FastAPI: sesión (Unit of Work por request), usuario actual
y verificación de permisos (deny por defecto)."""

import uuid
from collections.abc import Iterator

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
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


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_db),
) -> Usuario:
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado"
        ) from None
    usuario = UsuarioRepo(session).get(uuid.UUID(payload["sub"]))
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inválido")
    return usuario


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


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
