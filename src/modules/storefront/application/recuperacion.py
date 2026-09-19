"""Recuperar, restablecer y cambiar la clave de una cuenta del sitio (ADR-104).

Tres caminos, del más común al último recurso:

1. **Por correo** (`solicitar_recuperacion` → `restablecer_clave`): se manda un
   enlace de un solo uso que vence a los 30 minutos.
2. **Cambio voluntario o forzado** (`cambiar_clave`): quien ya está adentro, o
   quien entró con una clave temporal de atención al cliente y tiene que
   cambiarla antes de seguir.
3. **Por atención al cliente** (`atencion.restablecer_por_atencion`): para quien
   no tiene un correo al que llegue.

El enlace no vive en una tabla: es un JWT firmado con el secreto del sitio, con
audiencia propia (no sirve como token de sesión) y una huella de la clave
vigente, así que **deja de valer solo** al cambiarse la clave — un solo uso sin
guardar nada.
"""

import logging
import uuid

import jwt
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.storefront.application.errors import (
    CredencialesInvalidas,
    ReglaNegocio,
    TokenInvalido,
)
from src.modules.storefront.infrastructure.models import StorefrontCuenta
from src.modules.storefront.infrastructure.repositories import CuentaRepo, RefreshTokenRepo
from src.modules.storefront.infrastructure.security import (
    create_reset_token,
    decode_reset_token,
    hash_password,
    huella_de_clave,
    verify_password,
)
from src.shared import auditoria
from src.shared.integrations.email import smtp

log = logging.getLogger(__name__)

LARGO_MINIMO_CLAVE = 8


def _validar_clave(clave: str) -> None:
    if len(clave) < LARGO_MINIMO_CLAVE:
        raise ReglaNegocio(f"la clave debe tener al menos {LARGO_MINIMO_CLAVE} caracteres")


def _enlace(token: str) -> str:
    return f"{settings.storefront_sitio_url.rstrip('/')}/cuenta/restablecer?token={token}"


def _mensaje(cuenta: StorefrontCuenta, enlace: str) -> str:
    return (
        f"Hola {cuenta.nombres},\n\n"
        "Recibimos un pedido para cambiar la clave de tu cuenta en Charlie's Pizzas. "
        "Para elegir una nueva, entra a este enlace (vale por 30 minutos y solo una vez):\n\n"
        f"{enlace}\n\n"
        "Si no fuiste tú, ignora este mensaje: tu clave sigue igual.\n"
    )


def solicitar_recuperacion(session: Session, *, email: str) -> None:
    """Manda el enlace si la cuenta existe. **Siempre** termina igual, exista o
    no el correo: contestar distinto le diría a cualquiera qué correos tienen
    cuenta."""
    cuenta = CuentaRepo(session).get_by_email(email.strip().lower())
    if cuenta is None:
        return
    enlace = _enlace(create_reset_token(cuenta.id, cuenta.password_hash))
    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="storefront_cuenta",
        entidad_id=cuenta.id,
        accion="solicitar_recuperacion_clave",
        datos_despues={},
    )
    if not smtp.configurado():
        # Sin correo configurado nadie recibe nada: se deja constancia. El
        # enlace solo se escribe fuera de producción (es una credencial).
        log.warning(
            "Recuperación de clave sin SMTP configurado",
            extra={"cuenta_id": str(cuenta.id)},
        )
        if not settings.es_produccion:
            log.warning("Enlace de recuperación (solo desarrollo): %s", enlace)
        return
    try:
        smtp.enviar(
            destinatario=cuenta.email,
            asunto="Cambia tu clave de Charlie's Pizzas",
            cuerpo=_mensaje(cuenta, enlace),
        )
    except Exception:
        # Un correo caído no puede convertirse en una respuesta distinta (ni en
        # un 500 que delate que el correo existe): se registra y se sigue.
        log.exception(
            "No se pudo enviar el correo de recuperación", extra={"cuenta_id": str(cuenta.id)}
        )


def _cuenta_del_token(session: Session, token: str) -> StorefrontCuenta:
    try:
        datos = decode_reset_token(token)
    except jwt.PyJWTError as e:
        raise TokenInvalido("El enlace venció o no es válido. Pide uno nuevo.") from e
    try:
        cuenta_id = uuid.UUID(str(datos.get("sub")))
    except ValueError as e:
        raise TokenInvalido("El enlace no es válido. Pide uno nuevo.") from e
    cuenta = CuentaRepo(session).get(cuenta_id)
    # La huella de la clave vigente es lo que lo vuelve de un solo uso: si la
    # clave ya cambió, el token quedó de otra época.
    if cuenta is None or datos.get("ph") != huella_de_clave(cuenta.password_hash):
        raise TokenInvalido("El enlace venció o ya se usó. Pide uno nuevo.")
    return cuenta


def restablecer_clave(session: Session, *, token: str, password: str) -> None:
    _validar_clave(password)
    cuenta = _cuenta_del_token(session, token)
    fijar_clave(session, cuenta, password)
    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="storefront_cuenta",
        entidad_id=cuenta.id,
        accion="restablecer_clave",
        datos_despues={"via": "correo"},
    )


def fijar_clave(session: Session, cuenta: StorefrontCuenta, password: str) -> None:
    """Deja la cuenta con clave nueva, sin bloqueo ni cambio pendiente, y cierra
    todas las sesiones abiertas: quien la tenía robada ya no entra."""
    cuenta.password_hash = hash_password(password)
    cuenta.debe_cambiar_clave = False
    cuenta.intentos_fallidos = 0
    cuenta.bloqueado_hasta = None
    RefreshTokenRepo(session).revocar_cuenta(cuenta.id)


def cambiar_clave(
    session: Session,
    *,
    cuenta: StorefrontCuenta,
    clave_actual: str | None,
    clave_nueva: str,
) -> None:
    """Quien ya está adentro. Con clave puesta se exige la actual (un token
    robado no alcanza para cambiarla); una cuenta solo-Google, que nunca tuvo,
    puede ponerse una."""
    _validar_clave(clave_nueva)
    if cuenta.password_hash and (
        not clave_actual or not verify_password(cuenta.password_hash, clave_actual)
    ):
        raise CredencialesInvalidas("La clave actual no es correcta")
    cuenta.password_hash = hash_password(clave_nueva)
    cuenta.debe_cambiar_clave = False
    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="storefront_cuenta",
        entidad_id=cuenta.id,
        accion="cambiar_clave",
        datos_despues={},
    )
