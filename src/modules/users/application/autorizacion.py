"""Autorización puntual de supervisor sobre el terminal de otro (RN-AUD-005).

En caja hay acciones que el cajero **pide** pero no puede **autorizar**:
descontar, anular una línea ya enviada a cocina, cerrar con diferencia. La
forma real de resolverlo en el mostrador es que el supervisor se acerque y
teclee su PIN — no que el cajero cierre sesión y el supervisor entre.

Este módulo emite una **elevación de corta vida**: el supervisor se
identifica una vez, el backend verifica su PIN *y* que realmente tenga el
permiso, y devuelve un token acotado a esa acción. La operación siguiente lo
presenta y el servidor extrae de ahí quién autorizó.

Por qué un token y no un `autorizado_por` en el cuerpo: un identificador
suelto en el request es una firma falsificable. Cualquiera podría atribuir
un descuento al supervisor sin que el supervisor esté presente, y el reporte
de descuentos —que es la razón de ser del campo— dejaría de valer nada.

La elevación NO es una sesión: no sirve para llamar a cualquier endpoint,
no se refresca y muere en `AUTORIZACION_MINUTOS`.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.logging_config import logger_seguridad
from src.modules.users.application.errors import CredencialesInvalidas, TokenInvalido
from src.modules.users.domain import rules
from src.modules.users.infrastructure.repositories import UsuarioRepo
from src.modules.users.infrastructure.security import verify_pin
from src.shared import auditoria

log_seguridad = logger_seguridad()

# Ventana corta a propósito: cubre "el supervisor se acercó y tecleó",
# no "el supervisor autorizó algo hace media hora".
AUTORIZACION_MINUTOS = 3
TIPO_TOKEN = "autorizacion"


def emitir(
    session: Session,
    *,
    username: str,
    pin: str,
    permiso: str,
    ip: str | None = None,
) -> dict:
    """Verifica PIN + permiso del supervisor y devuelve la elevación.

    No incrementa el contador de intentos fallidos del login ni bloquea al
    usuario: es otro flujo. Sí deja rastro en `audit_log` y en el log de
    seguridad, que es donde se ve si alguien está probando PINes ajenos
    frente a una caja.
    """
    repo = UsuarioRepo(session)
    usuario = repo.get_by_username(username)
    autorizado = (
        usuario is not None
        and usuario.activo
        and verify_pin(usuario.pin_hash, pin)
        # `permite` respeta el comodín `*` del admin.
        and rules.permite(repo.permiso_codigos(usuario.id), permiso)
    )
    if not autorizado:
        # Mismo error tenga o no el permiso: distinguirlos revelaría qué
        # PIN es válido y qué usuario es supervisor.
        log_seguridad.warning(
            "Autorización de supervisor rechazada",
            extra={"username": username, "permiso": permiso, "ip": ip},
        )
        raise CredencialesInvalidas("Credenciales o permiso inválidos")

    auditoria.registrar(
        session,
        usuario_id=usuario.id,
        entidad="usuario",
        entidad_id=usuario.id,
        accion=f"autorizacion:{permiso}",
        ip=ip,
    )
    ahora = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(usuario.id),
            "typ": TIPO_TOKEN,
            "permiso": permiso,
            "iat": ahora,
            "exp": ahora + timedelta(minutes=AUTORIZACION_MINUTOS),
            "jti": str(uuid.uuid4()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {
        "autorizacion": token,
        "autorizado_por": usuario.id,
        "expira_en_minutos": AUTORIZACION_MINUTOS,
    }


def verificar(token: str, permiso: str) -> uuid.UUID:
    """Devuelve el `usuario_id` que autorizó, o lanza `TokenInvalido`.

    Comprueba el permiso pedido contra el del token: una elevación obtenida
    para descontar no puede reutilizarse para anular.
    """
    try:
        claims: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as e:
        raise TokenInvalido("Autorización inválida o expirada") from e
    if claims.get("typ") != TIPO_TOKEN:
        # Un access token normal no sirve como autorización: si sirviera,
        # el cajero se autorizaría a sí mismo con su propia sesión.
        raise TokenInvalido("El token presentado no es una autorización")
    if claims.get("permiso") != permiso:
        raise TokenInvalido(f"La autorización no cubre el permiso {permiso}")
    return uuid.UUID(claims["sub"])
