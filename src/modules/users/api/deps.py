"""Dependencias FastAPI: sesión (Unit of Work por request), usuario actual,
contexto de tenant (ADR-004) y verificación de permisos (deny por defecto)."""

import uuid
from collections.abc import Iterator

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.database import SessionLocal, SessionReportes
from src.core.tenant import Tenant
from src.modules.users.application import auth, tokens
from src.modules.users.application.errors import TokenInvalido
from src.modules.users.domain import rules
from src.modules.users.domain.rules import ContextoPermiso  # noqa: F401 — reexport
from src.modules.users.infrastructure.models import Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo
from src.modules.users.infrastructure.security import (
    decode_access_token,
    es_token_agente,
)

# `ContextoPermiso` queda re-exportado acá: `api.deps` es la única superficie
# de `users` que otro módulo puede importar (tests/test_arquitectura.py), así
# que el contrato público de `check_permission` vive completo en este archivo.

_bearer = HTTPBearer(auto_error=True)


def _sesion(factory) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """La sesión es la Unit of Work; los endpoints hacen commit explícito.
    Rollback automático ante excepción no controlada."""
    yield from _sesion(SessionLocal)


def get_db_reportes() -> Iterator[Session]:
    """Igual que `get_db`, sobre el engine de plazo largo (`SessionReportes`).

    La usan `src/core/reportes/` y el módulo `reports`, donde viven las
    consultas que legítimamente tardan (ver `docs/engineering/devops.md` →
    «Dos engines»). Es una función aparte y no un parámetro de `get_db` porque
    FastAPI resuelve y sobreescribe dependencias **por callable**: con un
    parámetro no habría manera de apuntar solo esta a otra base. El costo es
    que el `env` de un test que toque reportes sobreescribe las dos.
    """
    yield from _sesion(SessionReportes)


def get_claims(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_db),
) -> dict:
    """Claims validados de la credencial del request. FastAPI cachea la
    dependencia, así que se resuelve una sola vez por request.

    Dos credenciales, un solo juego de claims: el JWT del login humano se
    verifica por firma, y el token de una cuenta `agente_ia` (prefijo
    `prv_`) se busca en BD y se le arman los mismos claims. De acá para
    abajo —tenant, permisos, auditoría— nada distingue una de la otra.
    """
    if es_token_agente(creds.credentials):
        try:
            usuario = tokens.autenticar(session, creds.credentials)
        except TokenInvalido:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado"
            ) from None
        return auth.build_claims(session, usuario)
    try:
        return decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado"
        ) from None


# Lo único que se puede hacer con un PIN reseteado: mirarse a uno mismo,
# cambiarlo, y salir. Todo lo demás espera.
RUTAS_CON_PIN_TEMPORAL = frozenset(
    {
        "/api/v1/users/me",
        "/api/v1/users/me/pin",
        "/api/v1/auth/logout",
    }
)


def get_current_user(
    request: Request,
    claims: dict = Depends(get_claims),
    session: Session = Depends(get_db),
) -> Usuario:
    usuario = UsuarioRepo(session).get(uuid.UUID(claims["sub"]))
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inválido")
    # Se lee de la BD y no de un claim del token: así un reseteo surte efecto
    # en el request siguiente y no cuando vence el access token. También es lo
    # que hace que la obligación sea real — todo endpoint del ERP pasa por
    # acá (verificado: no hay handler con `get_tenant` y sin usuario), así que
    # no hay puerta lateral que quede abierta.
    if usuario.debe_cambiar_pin and request.url.path not in RUTAS_CON_PIN_TEMPORAL:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Tu PIN fue reseteado: elige uno nuevo antes de seguir",
        )
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


def check_permission(
    session: Session,
    usuario: Usuario,
    *codigos: str,
    contexto: rules.ContextoPermiso | None = None,
) -> None:
    """Igual que `require_permission` pero dentro del handler: para cuando el
    permiso exigido depende del body y no puede resolverse en un `Depends`.
    Basta con tener uno de `codigos`. Una sola consulta, a diferencia de
    llamar `tiene_permiso` en bucle.

    `contexto` evalúa `permiso.restricciones` (monto/estado/horario, ver
    `rules.cumple_restricciones`) contra los códigos que sí tiene: basta que
    UNO de ellos cumpla — mismo criterio OR que el permiso en sí. Sin
    `contexto`, el comportamiento es el de siempre (no evalúa restricciones).
    """
    repo = UsuarioRepo(session)
    concedidos = repo.permiso_codigos(usuario.id)
    otorgados = [codigo for codigo in codigos if rules.permite(concedidos, codigo)]
    if not otorgados:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado")
    if contexto is None:
        return
    for codigo in otorgados:
        if rules.cumple_restricciones(repo.restricciones(usuario.id, codigo), contexto):
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado por restricción")


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
