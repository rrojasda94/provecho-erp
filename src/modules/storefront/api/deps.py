"""Dependencias FastAPI propias de la cuenta del sitio (ADR-104).

`get_db` se reusa de `users.api.deps` (contrato público entre módulos,
`api.deps`) — es una sesión de base genérica, no algo específico de la
credencial del ERP; mismo criterio que ya aplican
`storefront.api.routers`/`publico_routers` (PR1). Lo que sí es propio de
acá, y nunca se reusa de `users`, es la extracción y verificación del
Bearer: la cuenta web tiene su propio secreto y su propia `aud`
(`infrastructure.security`), y por eso su propio `get_claims`.
"""

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.modules.storefront.infrastructure.models import StorefrontCuenta
from src.modules.storefront.infrastructure.repositories import CuentaRepo
from src.modules.storefront.infrastructure.security import decode_access_token
from src.modules.users.api.deps import get_db

__all__ = ["get_claims", "get_cuenta_actual", "get_db"]

_bearer = HTTPBearer(auto_error=True)


def get_claims(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        return decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado"
        ) from None


def get_cuenta_actual(
    claims: dict = Depends(get_claims), session: Session = Depends(get_db)
) -> StorefrontCuenta:
    cuenta = CuentaRepo(session).get(uuid.UUID(claims["sub"]))
    if cuenta is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cuenta inválida")
    return cuenta
