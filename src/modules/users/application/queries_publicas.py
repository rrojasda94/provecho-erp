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
