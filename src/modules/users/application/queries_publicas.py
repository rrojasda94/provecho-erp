"""Contrato público de lectura de `users`, para el resto de los módulos.

Mismo patrón que `sales.application.queries_publicas`: lo que otro módulo
puede consultar de users pasa por acá y no por su dominio ni por sus
repositorios. `purchases` y `accounting` necesitan saber si el actor puede
aprobar por encima del umbral *sin* que eso sea un `require_permission`
(el endpoint se atiende igual; lo que cambia es si la orden queda aprobada
o pendiente), y para responderlo importaban `users.domain.rules`.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.users.application import auth, notificaciones
from src.modules.users.application.errors import (
    CredencialesInvalidas,
    UsuarioBloqueado,
)
from src.modules.users.domain import rules
from src.modules.users.infrastructure.models import Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo


def tiene_permiso(session: Session, usuario_id: uuid.UUID, codigo: str) -> bool:
    """¿El usuario tiene el permiso `codigo` (o el comodín `*`)?"""
    return rules.permite(UsuarioRepo(session).permiso_codigos(usuario_id), codigo)


def permisos_de(session: Session, usuario_id: uuid.UUID) -> set[str]:
    """Todos los códigos de permiso del usuario, en una consulta.

    Para quien tiene que **filtrar una lista** por permiso en vez de negar un
    acceso: `reports` recorta su catálogo de emisiones contra esto, igual que
    `core/reportes` recorta el suyo. Preguntar con `tiene_permiso` en bucle
    sería una consulta por entrada del catálogo para armar una sola pantalla.

    Devuelve el comodín `*` tal cual si lo tiene: interpretarlo es de quien
    filtra (`rules.permite` y los `visibles()` de cada catálogo ya lo hacen).
    """
    return set(UsuarioRepo(session).permiso_codigos(usuario_id))


def obtener_usuario(session: Session, usuario_id: uuid.UUID) -> Usuario | None:
    """Para cuando otro módulo necesita el `Usuario` completo de un id que
    ya validó por otra vía (ej. `autorizacion.verificar`, que solo devuelve
    el id) — típicamente para pasarlo a `check_permission` con `contexto`."""
    return UsuarioRepo(session).get(usuario_id)


# Resultados de `verificar_pin_de`. Son strings y no excepciones porque
# quien pregunta está en otro módulo y no puede importar los errores de
# users sin romper el límite (`tests/test_arquitectura.py`).
PIN_OK = "ok"
PIN_INVALIDO = "invalido"
PIN_BLOQUEADO = "bloqueado"


def verificar_pin_de(
    session: Session, usuario_id: uuid.UUID, pin: str, ip: str | None = None
) -> str:
    """¿Este PIN es el de este usuario? Contra el MISMO lockout del login.

    Es el contrato que pedía la auditoría: hasta ahora, verificar un PIN
    ajeno obligaba a entrar a `users.application` desde afuera. Lo necesita
    el pad de asistencia, donde quien teclea no es el dueño de la sesión —
    la tablet está logueada con la cuenta del terminal y el PIN es del
    trabajador que marca (RN-RRHH-020).

    El intento fallido queda escrito en la sesión (contador y bloqueo): el
    llamador tiene que hacer `commit` también cuando la respuesta es
    negativa, o el lockout no cuenta nada.

    Devuelve `PIN_OK`, `PIN_INVALIDO` o `PIN_BLOQUEADO`. Un usuario
    inexistente o inactivo devuelve `PIN_INVALIDO`, sin distinguirlo de un
    PIN errado: la diferencia solo serviría para enumerar cuentas.
    """
    usuario = UsuarioRepo(session).get(usuario_id)
    if usuario is None or not usuario.activo:
        return PIN_INVALIDO
    try:
        auth.verificar_pin(session, usuario, pin, ip)
    except UsuarioBloqueado:
        return PIN_BLOQUEADO
    except CredencialesInvalidas:
        return PIN_INVALIDO
    return PIN_OK


def notificar_a(
    session: Session,
    usuario_id: uuid.UUID,
    *,
    tipo: str,
    titulo: str,
    cuerpo: str | None = None,
    nivel: str = "aviso",
    sucursal_id: uuid.UUID | None = None,
) -> None:
    """Deja un aviso en la bandeja de UNA persona.

    Distinto de emitir un reporte: el reporte va a quien responde por el
    hecho y exige el permiso del módulo dueño para abrirlo (RN-REP-002). Un
    trabajador de cocina no tiene `rrhh.leer` y nunca lo va a tener, pero el
    «te falta marcar la salida» es justamente para él. Su campana no pide
    permisos: es suya.

    No hace `commit`: es de quien abrió la sesión.
    """
    notificaciones.notificar(
        session,
        [usuario_id],
        tipo=tipo,
        titulo=titulo,
        cuerpo=cuerpo,
        nivel=nivel,
        sucursal_id=sucursal_id,
    )
