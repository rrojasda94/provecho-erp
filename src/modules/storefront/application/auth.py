"""Casos de uso de autenticación de cuenta del sitio (ADR-104): registro por
email/clave o Google, login, refresh (rotación + detección de reuso) y
logout. Mismo mecanismo que `users.application.auth`, sobre su propia tabla
y su propio secreto — nunca importa `users`.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.storefront.application.errors import (
    Conflicto,
    CredencialesInvalidas,
    CuentaBloqueada,
    ReglaNegocio,
    TokenInvalido,
)
from src.modules.storefront.domain import rules
from src.modules.storefront.infrastructure.google_auth import (
    GoogleTokenInvalido,
    verificar_id_token,
)
from src.modules.storefront.infrastructure.models import (
    StorefrontCuenta,
    StorefrontDireccion,
    StorefrontRefreshToken,
)
from src.modules.storefront.infrastructure.repositories import (
    CuentaRepo,
    DireccionRepo,
    RefreshTokenRepo,
)
from src.modules.storefront.infrastructure.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_expira_en,
    verify_password,
)
from src.shared import auditoria


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def build_claims(cuenta: StorefrontCuenta) -> dict:
    return {"sub": str(cuenta.id), "email": cuenta.email}


def _emitir_tokens(session: Session, cuenta: StorefrontCuenta, sesion_id: uuid.UUID) -> dict:
    raw_refresh, token_hash = new_refresh_token()
    RefreshTokenRepo(session).add(
        StorefrontRefreshToken(
            cuenta_id=cuenta.id, token_hash=token_hash, sesion_id=sesion_id,
            expira_en=refresh_expira_en(),
        )
    )
    access = create_access_token(build_claims(cuenta))
    return {"access_token": access, "refresh_token": raw_refresh, "token_type": "bearer"}


def _publicar_cuenta_registrada(
    session: Session,
    cuenta: StorefrontCuenta,
    *,
    direccion: str | None,
    ubicacion: dict | None,
) -> None:
    """Dispara el enlace hacia `sales.cliente` (ADR-104). Post-commit y
    best-effort (ADR-016): si el listener de `sales` falla, la cuenta queda
    sin `cliente_id` hasta la reconciliación — nunca bloquea el registro."""
    event_bus.publish(
        "storefront.cuenta_registrada",
        {
            "cuenta_id": str(cuenta.id),
            "marca_id": settings.storefront_marca_id or None,
            "nombres": cuenta.nombres,
            "apellidos": cuenta.apellidos,
            "tipo_documento": cuenta.tipo_documento,
            "numero_documento": cuenta.numero_documento,
            "telefono": cuenta.telefono,
            "email": cuenta.email,
            "fecha_nacimiento": (
                cuenta.fecha_nacimiento.isoformat() if cuenta.fecha_nacimiento else None
            ),
            "direccion": direccion,
            "ubicacion": ubicacion,
        },
        session=session,
    )


def _crear_cuenta(
    session: Session,
    *,
    email: str,
    password_hash: str | None,
    google_sub: str | None,
    nombres: str,
    apellidos: str,
    tipo_documento: str | None,
    numero_documento: str | None,
    telefono: str | None,
    fecha_nacimiento: date | None,
    direccion: str | None,
    ubicacion: dict | None,
) -> StorefrontCuenta:
    email = email.strip().lower()
    if CuentaRepo(session).get_by_email(email) is not None:
        raise Conflicto("ya existe una cuenta con ese email")

    cuenta = CuentaRepo(session).add(
        StorefrontCuenta(
            email=email, password_hash=password_hash, google_sub=google_sub,
            nombres=nombres.strip(), apellidos=apellidos.strip() or "-",
            tipo_documento=tipo_documento, numero_documento=numero_documento,
            telefono=telefono, fecha_nacimiento=fecha_nacimiento,
        )
    )
    if direccion:
        DireccionRepo(session).add(
            StorefrontDireccion(
                cuenta_id=cuenta.id, etiqueta="Principal", direccion=direccion,
                predeterminada=True, **(ubicacion or {}),
            )
        )
    # `usuario_id=None`: nadie del ERP actúa acá, es autoservicio del sitio.
    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="storefront_cuenta",
        entidad_id=cuenta.id,
        accion="crear_cuenta",
        datos_despues={
            "email": email,
            "via": "google" if google_sub else "clave",
        },
    )
    _publicar_cuenta_registrada(session, cuenta, direccion=direccion, ubicacion=ubicacion)
    return cuenta


def registrar(
    session: Session,
    *,
    email: str,
    password: str,
    nombres: str,
    apellidos: str,
    tipo_documento: str,
    numero_documento: str,
    telefono: str,
    fecha_nacimiento: date,
    direccion: str | None = None,
    ubicacion: dict | None = None,
) -> dict:
    if len(password) < 8:
        raise ReglaNegocio("la clave debe tener al menos 8 caracteres")
    cuenta = _crear_cuenta(
        session, email=email, password_hash=hash_password(password), google_sub=None,
        nombres=nombres, apellidos=apellidos, tipo_documento=tipo_documento,
        numero_documento=numero_documento, telefono=telefono,
        fecha_nacimiento=fecha_nacimiento, direccion=direccion, ubicacion=ubicacion,
    )
    return _emitir_tokens(session, cuenta, uuid.uuid4())


def login(session: Session, *, email: str, password: str) -> dict:
    cuenta = CuentaRepo(session).get_by_email(email)
    # Anti-enumeración: mismo error para email inexistente, cuenta solo-Google
    # (sin `password_hash`) y clave incorrecta.
    if cuenta is None or not cuenta.password_hash:
        raise CredencialesInvalidas("Credenciales inválidas")

    ahora = datetime.now(UTC)
    if cuenta.bloqueado_hasta and _aware(cuenta.bloqueado_hasta) > ahora:
        raise CuentaBloqueada("Cuenta bloqueada por intentos fallidos")

    if not verify_password(cuenta.password_hash, password):
        cuenta.intentos_fallidos += 1
        if cuenta.intentos_fallidos >= rules.MAX_INTENTOS_FALLIDOS:
            cuenta.bloqueado_hasta = ahora + rules.DURACION_BLOQUEO
            cuenta.intentos_fallidos = 0
            raise CuentaBloqueada("Cuenta bloqueada por intentos fallidos")
        raise CredencialesInvalidas("Credenciales inválidas")

    cuenta.intentos_fallidos = 0
    cuenta.bloqueado_hasta = None
    return _emitir_tokens(session, cuenta, uuid.uuid4())


def login_google(
    session: Session,
    *,
    id_token: str,
    nombres: str | None = None,
    apellidos: str | None = None,
    tipo_documento: str | None = None,
    numero_documento: str | None = None,
    telefono: str | None = None,
    fecha_nacimiento: date | None = None,
    direccion: str | None = None,
    ubicacion: dict | None = None,
) -> dict:
    try:
        datos = verificar_id_token(id_token)
    except GoogleTokenInvalido as e:
        raise CredencialesInvalidas(str(e)) from e

    repo = CuentaRepo(session)
    cuenta = repo.get_by_google_sub(datos["sub"])
    if cuenta is not None:
        return _emitir_tokens(session, cuenta, uuid.uuid4())

    existente = repo.get_by_email(datos["email"])
    if existente is not None:
        # Ya tenía cuenta por email/clave: se vincula Google a la misma
        # cuenta en vez de duplicarla — es la misma persona con el mismo
        # correo verificado por Google.
        existente.google_sub = datos["sub"]
        return _emitir_tokens(session, existente, uuid.uuid4())

    # Cuenta nueva vía Google: igual se piden los datos que exige el enlace a
    # `cliente` (RN-WEB-005) — Google solo confirma el email, no el DNI, el
    # teléfono ni el cumpleaños.
    faltantes = [
        campo
        for campo, valor in (
            ("tipo_documento", tipo_documento), ("numero_documento", numero_documento),
            ("telefono", telefono), ("fecha_nacimiento", fecha_nacimiento),
            ("direccion", direccion),
        )
        if not valor
    ]
    if faltantes:
        raise ReglaNegocio(
            "faltan datos para crear la cuenta: " + ", ".join(faltantes)
        )
    cuenta = _crear_cuenta(
        session, email=datos["email"], password_hash=None, google_sub=datos["sub"],
        nombres=nombres or datos["nombres"], apellidos=apellidos or datos["apellidos"],
        tipo_documento=tipo_documento, numero_documento=numero_documento,
        telefono=telefono, fecha_nacimiento=fecha_nacimiento, direccion=direccion,
        ubicacion=ubicacion,
    )
    return _emitir_tokens(session, cuenta, uuid.uuid4())


def refresh(session: Session, raw_token: str) -> dict:
    repo = RefreshTokenRepo(session)
    rec = repo.get_by_hash(hash_refresh_token(raw_token))
    if rec is None:
        raise TokenInvalido("Refresh token inválido")

    if rec.revocado:
        repo.revocar_sesion(rec.sesion_id)
        raise TokenInvalido("Refresh token reutilizado; sesión revocada")

    if _aware(rec.expira_en) <= datetime.now(UTC):
        rec.revocado = True
        raise TokenInvalido("Refresh token expirado")

    cuenta = CuentaRepo(session).get(rec.cuenta_id)
    if cuenta is None:
        raise TokenInvalido("Cuenta inválida")

    rec.revocado = True
    return _emitir_tokens(session, cuenta, rec.sesion_id)


def logout(session: Session, raw_token: str) -> None:
    repo = RefreshTokenRepo(session)
    rec = repo.get_by_hash(hash_refresh_token(raw_token))
    if rec is not None:
        repo.revocar_sesion(rec.sesion_id)
