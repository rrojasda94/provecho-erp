"""Casos de uso de autenticación: login, refresh (rotación + detección de
reuso), logout y construcción de claims del JWT."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.core.logging_config import logger_seguridad
from src.modules.users.application.errors import (
    CredencialesInvalidas,
    TokenInvalido,
    UsuarioBloqueado,
)
from src.modules.users.domain import rules
from src.modules.users.infrastructure.models import RefreshToken, Sucursal, Usuario
from src.modules.users.infrastructure.repositories import (
    RefreshTokenRepo,
    UsuarioRepo,
)
from src.modules.users.infrastructure.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    refresh_expira_en,
    verify_pin,
)
from src.shared import auditoria

log_seguridad = logger_seguridad()


def _aware(dt: datetime | None) -> datetime | None:
    """Normaliza a UTC-aware (SQLite devuelve naive; Postgres aware)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _empresa_id(session: Session, sucursal_ids: list[uuid.UUID]) -> uuid.UUID | None:
    if not sucursal_ids:
        return None
    empresas = set(
        session.scalars(
            select(Sucursal.empresa_id).where(Sucursal.id.in_(sucursal_ids))
        )
    )
    return empresas.pop() if len(empresas) == 1 else None


def build_claims(session: Session, usuario: Usuario) -> dict:
    repo = UsuarioRepo(session)
    sucursales = repo.sucursal_ids(usuario.id)
    return {
        "sub": str(usuario.id),
        "tipo": usuario.tipo,
        "roles": repo.rol_nombres(usuario.id),
        "sucursales": [str(s) for s in sucursales],
        "empresa_id": str(_empresa_id(session, sucursales) or "") or None,
        # Superusuario (permiso `*`): puede operar sobre una empresa que
        # indique explícitamente cuando no tiene sucursales asignadas — es la
        # cuenta de administración, que existe antes que cualquier sucursal.
        # Se resuelve al emitir el token; revocar `*` surte efecto al vencer
        # el access token (minutos). El permiso concreto de cada endpoint sí
        # se valida contra BD en cada request.
        "su": rules.permite(repo.permiso_codigos(usuario.id), "*"),
    }


def _emitir_tokens(session: Session, usuario: Usuario, sesion_id: uuid.UUID) -> dict:
    raw_refresh, token_hash = new_refresh_token()
    RefreshTokenRepo(session).add(
        RefreshToken(
            usuario_id=usuario.id,
            token_hash=token_hash,
            sesion_id=sesion_id,
            expira_en=refresh_expira_en(),
        )
    )
    access = create_access_token(build_claims(session, usuario))
    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


def _registrar_pin_fallido(
    session: Session, usuario: Usuario, ahora: datetime, ip: str | None, accion: str
) -> None:
    """Suma el intento, bloquea al llegar al tope y deja el rastro.

    Vive acá y no en `login` porque todo camino que reciba un PIN tiene que
    contar contra el MISMO lockout: si el desbloqueo del PDV llevara su
    propio contador, sería el camino cómodo para probar PINes sin agotar
    los cinco intentos del login.
    """
    usuario.intentos_fallidos += 1
    recien_bloqueado = usuario.intentos_fallidos >= rules.MAX_INTENTOS_FALLIDOS
    if recien_bloqueado:
        usuario.bloqueado_hasta = ahora + rules.DURACION_BLOQUEO
        usuario.intentos_fallidos = 0
    auditoria.registrar(
        session, usuario_id=usuario.id, entidad="usuario", entidad_id=usuario.id,
        accion=accion, ip=ip,
    )
    # El `audit_log` deja el rastro legal; el log de seguridad es lo que
    # dispara una alerta cuando alguien está probando credenciales.
    log_seguridad.warning(
        "PIN fallido (%s)%s",
        accion,
        " — usuario bloqueado" if recien_bloqueado else "",
        extra={
            "usuario_id": str(usuario.id),
            "ip": ip,
            "intentos": usuario.intentos_fallidos,
            "bloqueado": recien_bloqueado,
        },
    )
    if recien_bloqueado:
        raise UsuarioBloqueado("Usuario bloqueado por intentos fallidos")


def verificar_pin(
    session: Session, usuario: Usuario, pin: str, ip: str | None = None
) -> None:
    """¿Sigue siendo la misma persona frente al terminal? (RN-POS-014)

    No emite tokens ni exige un código de permiso: solo responde si el PIN
    es el de quien ya tiene la sesión abierta. `login` rotaría la sesión y
    perdería el borrador del PDV; `autorizar` está para elevar a OTRO. Este
    solo confirma identidad, que es lo que pide desbloquear una pantalla.
    """
    ahora = datetime.now(UTC)
    if usuario.bloqueado_hasta and _aware(usuario.bloqueado_hasta) > ahora:
        raise UsuarioBloqueado("Usuario bloqueado por intentos fallidos")
    if not verify_pin(usuario.pin_hash, pin):
        _registrar_pin_fallido(session, usuario, ahora, ip, "desbloqueo_fallido")
        raise CredencialesInvalidas("Credenciales inválidas")
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None


def login(session: Session, username: str, pin: str, ip: str | None = None) -> dict:
    repo = UsuarioRepo(session)
    usuario = repo.get_by_username(username)

    # Usuario inexistente: mismo error, sin filtrar existencia (anti-enumeración).
    if usuario is None or not usuario.activo:
        raise CredencialesInvalidas("Credenciales inválidas")

    ahora = datetime.now(UTC)
    if usuario.bloqueado_hasta and _aware(usuario.bloqueado_hasta) > ahora:
        raise UsuarioBloqueado("Usuario bloqueado por intentos fallidos")

    if not verify_pin(usuario.pin_hash, pin):
        _registrar_pin_fallido(session, usuario, ahora, ip, "login_fallido")
        raise CredencialesInvalidas("Credenciales inválidas")

    # Éxito: resetear lockout y emitir tokens.
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    tokens = _emitir_tokens(session, usuario, uuid.uuid4())
    auditoria.registrar(
        session, usuario_id=usuario.id, entidad="usuario", entidad_id=usuario.id,
        accion="login", ip=ip,
    )
    event_bus.publish("users.sesion_iniciada", {"usuario_id": str(usuario.id)}, session=session)
    return tokens


def refresh(session: Session, raw_token: str) -> dict:
    repo = RefreshTokenRepo(session)
    rec = repo.get_by_hash(hash_refresh_token(raw_token))
    if rec is None:
        raise TokenInvalido("Refresh token inválido")

    # Reuso de un token ya rotado/revocado: revoca toda la cadena.
    if rec.revocado:
        repo.revocar_sesion(rec.sesion_id)
        # Señal fuerte de token robado: alguien usó una copia ya rotada.
        log_seguridad.error(
            "Reuso de refresh token; sesión revocada",
            extra={"usuario_id": str(rec.usuario_id), "sesion_id": str(rec.sesion_id)},
        )
        raise TokenInvalido("Refresh token reutilizado; sesión revocada")

    if _aware(rec.expira_en) <= datetime.now(UTC):
        rec.revocado = True
        raise TokenInvalido("Refresh token expirado")

    usuario = UsuarioRepo(session).get(rec.usuario_id)
    if usuario is None or not usuario.activo:
        raise TokenInvalido("Usuario inválido")

    rec.revocado = True  # rotación
    return _emitir_tokens(session, usuario, rec.sesion_id)


def logout(session: Session, raw_token: str) -> None:
    """Idempotente: revoca la sesión del token si existe."""
    repo = RefreshTokenRepo(session)
    rec = repo.get_by_hash(hash_refresh_token(raw_token))
    if rec is not None:
        repo.revocar_sesion(rec.sesion_id)
