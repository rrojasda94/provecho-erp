"""Casos de uso de administración (solo admin): CRUD de usuarios, roles,
permisos y asignaciones. Los cambios de roles/permisos se auditan."""

import uuid

from sqlalchemy.orm import Session

from src.modules.users.application.errors import (
    Conflicto,
    NoEncontrado,
    PinInvalido,
)
from src.modules.users.domain import rules
from src.modules.users.infrastructure.models import (
    Permiso,
    Rol,
    RolPermiso,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.repositories import (
    AuditLogRepo,
    PermisoRepo,
    RolRepo,
    UsuarioRepo,
)
from src.modules.users.infrastructure.security import hash_pin


# --- Usuarios ---------------------------------------------------------------
def crear_usuario(
    session: Session,
    *,
    username: str,
    pin: str,
    tipo: str = "humano",
    persona_id: uuid.UUID | None = None,
    nombre_display: str | None = None,
    email: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Usuario:
    repo = UsuarioRepo(session)
    if repo.get_by_username(username):
        raise Conflicto(f"username '{username}' ya existe")
    # ponytail: PIN obligatorio también para agente_ia; su auth por token es a futuro.
    if not rules.pin_valido(pin):
        raise PinInvalido(f"El PIN debe ser {rules.PIN_LENGTH} dígitos")
    usuario = repo.add(
        Usuario(
            username=username,
            pin_hash=hash_pin(pin),
            tipo=tipo,
            persona_id=persona_id,
            nombre_display=nombre_display,
            email=email,
        )
    )
    AuditLogRepo(session).registrar(
        usuario_id=actor_id, entidad="usuario", entidad_id=usuario.id,
        accion="crear", datos_despues={"username": username, "tipo": tipo},
    )
    return usuario


def editar_usuario(
    session: Session, usuario_id: uuid.UUID, **campos
) -> Usuario:
    usuario = _get(UsuarioRepo(session).get(usuario_id), "usuario")
    for campo in ("nombre_display", "email", "activo", "persona_id"):
        if campo in campos and campos[campo] is not None:
            setattr(usuario, campo, campos[campo])
    return usuario


def cambiar_pin(session: Session, usuario_id: uuid.UUID, nuevo_pin: str) -> Usuario:
    usuario = _get(UsuarioRepo(session).get(usuario_id), "usuario")
    if not rules.pin_valido(nuevo_pin):
        raise PinInvalido(f"El PIN debe ser {rules.PIN_LENGTH} dígitos")
    usuario.pin_hash = hash_pin(nuevo_pin)
    return usuario


def listar_usuarios(session: Session) -> list[Usuario]:
    return UsuarioRepo(session).list()


# --- Roles ------------------------------------------------------------------
def crear_rol(
    session: Session, *, nombre: str, descripcion: str | None = None
) -> Rol:
    repo = RolRepo(session)
    if repo.get_by_nombre(nombre):
        raise Conflicto(f"rol '{nombre}' ya existe")
    return repo.add(Rol(nombre=nombre, descripcion=descripcion))


def listar_roles(session: Session) -> list[Rol]:
    return RolRepo(session).list()


# --- Permisos ---------------------------------------------------------------
def crear_permiso(
    session: Session,
    *,
    codigo: str,
    descripcion: str | None = None,
    restricciones: dict | None = None,
) -> Permiso:
    repo = PermisoRepo(session)
    if repo.get_by_codigo(codigo):
        raise Conflicto(f"permiso '{codigo}' ya existe")
    return repo.add(
        Permiso(codigo=codigo, descripcion=descripcion, restricciones=restricciones)
    )


def listar_permisos(session: Session) -> list[Permiso]:
    return PermisoRepo(session).list()


# --- Asignaciones -----------------------------------------------------------
def asignar_rol(
    session: Session,
    usuario_id: uuid.UUID,
    rol_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> None:
    _get(UsuarioRepo(session).get(usuario_id), "usuario")
    _get(RolRepo(session).get(rol_id), "rol")
    if session.get(UsuarioRol, (usuario_id, rol_id)) is None:
        session.add(UsuarioRol(usuario_id=usuario_id, rol_id=rol_id))
        AuditLogRepo(session).registrar(
            usuario_id=actor_id, entidad="usuario_rol", entidad_id=usuario_id,
            accion="asignar_rol", datos_despues={"rol_id": str(rol_id)},
        )


def quitar_rol(session: Session, usuario_id: uuid.UUID, rol_id: uuid.UUID) -> None:
    fila = session.get(UsuarioRol, (usuario_id, rol_id))
    if fila is not None:
        session.delete(fila)


def asignar_permiso(
    session: Session,
    rol_id: uuid.UUID,
    permiso_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> None:
    _get(RolRepo(session).get(rol_id), "rol")
    _get(PermisoRepo(session).get(permiso_id), "permiso")
    if session.get(RolPermiso, (rol_id, permiso_id)) is None:
        session.add(RolPermiso(rol_id=rol_id, permiso_id=permiso_id))
        AuditLogRepo(session).registrar(
            usuario_id=actor_id, entidad="rol_permiso", entidad_id=rol_id,
            accion="asignar_permiso", datos_despues={"permiso_id": str(permiso_id)},
        )


def quitar_permiso(session: Session, rol_id: uuid.UUID, permiso_id: uuid.UUID) -> None:
    fila = session.get(RolPermiso, (rol_id, permiso_id))
    if fila is not None:
        session.delete(fila)


def asignar_sucursal(
    session: Session, usuario_id: uuid.UUID, sucursal_id: uuid.UUID
) -> None:
    _get(UsuarioRepo(session).get(usuario_id), "usuario")
    if session.get(UsuarioSucursal, (usuario_id, sucursal_id)) is None:
        session.add(
            UsuarioSucursal(usuario_id=usuario_id, sucursal_id=sucursal_id)
        )


def quitar_sucursal(
    session: Session, usuario_id: uuid.UUID, sucursal_id: uuid.UUID
) -> None:
    fila = session.get(UsuarioSucursal, (usuario_id, sucursal_id))
    if fila is not None:
        session.delete(fila)


def _get(obj, nombre: str):
    if obj is None:
        raise NoEncontrado(f"{nombre} no encontrado")
    return obj
