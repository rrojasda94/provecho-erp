"""Tokens de API para cuentas `agente_ia`: alta, listado, revocación y
verificación en cada request.

Por qué existe (ver `README.md` → Autenticación de agentes): un agente no
teclea un PIN ni refresca una sesión cada 15 minutos. Le damos una
credencial larga, sin caducidad obligatoria, revocable de a una — y el
resto del RBAC no cambia: el token dice *quién*, los roles siguen diciendo
*qué puede*.

Solo `tipo=agente_ia` puede tener token. Un humano con una credencial de
larga vida sin lockout ni rotación es exactamente lo que el login evita.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.core.logging_config import logger_seguridad
from src.modules.users.application.errors import (
    Conflicto,
    NoEncontrado,
    TokenInvalido,
)
from src.modules.users.infrastructure.models import TokenAgente, Usuario
from src.modules.users.infrastructure.repositories import (
    AuditLogRepo,
    TokenAgenteRepo,
    UsuarioRepo,
)
from src.modules.users.infrastructure.security import hash_api_token, new_api_token

log_seguridad = logger_seguridad()

# Granularidad de `ultimo_uso_en`: sirve para "¿este token sigue vivo?", no
# para auditar llamada por llamada (eso es `audit_log`). Escribir en cada
# request convertiría cada GET del agente en un UPDATE.
FRECUENCIA_ULTIMO_USO = timedelta(hours=1)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite devuelve naive; Postgres aware (mismo criterio que `auth`)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def crear(
    session: Session,
    usuario_id: uuid.UUID,
    *,
    nombre: str,
    dias_validez: int | None = None,
    actor_id: uuid.UUID | None = None,
) -> tuple[TokenAgente, str]:
    """Devuelve (fila, token_en_claro). El claro se muestra una sola vez:
    después solo queda su hash, y perderlo obliga a emitir otro."""
    usuario = UsuarioRepo(session).get(usuario_id)
    if usuario is None or not usuario.activo:
        raise NoEncontrado("usuario no encontrado")
    if usuario.tipo != "agente_ia":
        raise Conflicto("solo un usuario tipo agente_ia puede tener token de API")

    raw, prefijo, token_hash = new_api_token()
    fila = TokenAgenteRepo(session).add(
        TokenAgente(
            usuario_id=usuario_id,
            nombre=nombre,
            prefijo=prefijo,
            token_hash=token_hash,
            expira_en=(
                datetime.now(UTC) + timedelta(days=dias_validez)
                if dias_validez
                else None
            ),
        )
    )
    AuditLogRepo(session).registrar(
        usuario_id=actor_id, entidad="token_agente", entidad_id=fila.id,
        accion="crear", datos_despues={"usuario_id": str(usuario_id), "prefijo": prefijo},
    )
    return fila, raw


def listar(session: Session, usuario_id: uuid.UUID) -> list[TokenAgente]:
    if UsuarioRepo(session).get(usuario_id) is None:
        raise NoEncontrado("usuario no encontrado")
    return TokenAgenteRepo(session).list(usuario_id)


def revocar(
    session: Session,
    usuario_id: uuid.UUID,
    token_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Idempotente: revocar dos veces el mismo token no es un error."""
    repo = TokenAgenteRepo(session)
    fila = repo.get(token_id)
    if fila is None or fila.usuario_id != usuario_id:
        raise NoEncontrado("token no encontrado")
    if fila.revocado:
        return
    fila.revocado = True
    AuditLogRepo(session).registrar(
        usuario_id=actor_id, entidad="token_agente", entidad_id=fila.id,
        accion="revocar", datos_despues={"prefijo": fila.prefijo},
    )
    log_seguridad.info(
        "Token de agente revocado",
        extra={"usuario_id": str(fila.usuario_id), "prefijo": fila.prefijo},
    )


def autenticar(session: Session, raw: str) -> Usuario:
    """Resuelve el usuario detrás de un token de API, o lanza `TokenInvalido`.

    Un solo mensaje para todos los motivos (inexistente, revocado, vencido,
    usuario apagado): el mismo criterio anti-enumeración del login.
    """
    fila = TokenAgenteRepo(session).get_by_hash(hash_api_token(raw))
    ahora = datetime.now(UTC)
    if fila is None or fila.revocado:
        raise TokenInvalido("Token de API inválido")
    if fila.expira_en is not None and _aware(fila.expira_en) <= ahora:
        raise TokenInvalido("Token de API inválido")

    usuario = UsuarioRepo(session).get(fila.usuario_id)
    # `tipo` se revalida acá y no solo al crear: convertir la cuenta a
    # humana tiene que apagar sus tokens sin depender de que alguien los
    # revoque a mano.
    if usuario is None or not usuario.activo or usuario.tipo != "agente_ia":
        raise TokenInvalido("Token de API inválido")

    if (
        fila.ultimo_uso_en is None
        or ahora - _aware(fila.ultimo_uso_en) > FRECUENCIA_ULTIMO_USO
    ):
        fila.ultimo_uso_en = ahora
        # Commit propio: esto pasa en una dependencia, antes de que el
        # endpoint abra su Unit of Work, y un GET puede no commitear nunca.
        session.commit()
    return usuario
