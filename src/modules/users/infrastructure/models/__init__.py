"""Modelos del módulo users: persona, organización, usuario y RBAC/auth
(data-model §1, §2)."""

from src.modules.users.infrastructure.models.almacen import Almacen
from src.modules.users.infrastructure.models.audit_log import AuditLog
from src.modules.users.infrastructure.models.empresa import Empresa
from src.modules.users.infrastructure.models.grupo import Grupo
from src.modules.users.infrastructure.models.licencia_marca import LicenciaMarca
from src.modules.users.infrastructure.models.marca import Marca
from src.modules.users.infrastructure.models.permiso import Permiso
from src.modules.users.infrastructure.models.persona import Persona
from src.modules.users.infrastructure.models.refresh_token import RefreshToken
from src.modules.users.infrastructure.models.rol import Rol
from src.modules.users.infrastructure.models.rol_permiso import RolPermiso
from src.modules.users.infrastructure.models.sucursal import Sucursal
from src.modules.users.infrastructure.models.usuario import Usuario
from src.modules.users.infrastructure.models.usuario_rol import UsuarioRol
from src.modules.users.infrastructure.models.usuario_sucursal import UsuarioSucursal

__all__ = [
    "Almacen",
    "AuditLog",
    "Empresa",
    "Grupo",
    "LicenciaMarca",
    "Marca",
    "Permiso",
    "Persona",
    "RefreshToken",
    "Rol",
    "RolPermiso",
    "Sucursal",
    "Usuario",
    "UsuarioRol",
    "UsuarioSucursal",
]
