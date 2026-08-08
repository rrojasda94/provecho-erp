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
    Almacen,
    Marca,
    Permiso,
    Persona,
    Rol,
    RolPermiso,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.repositories import (
    AlmacenRepo,
    MarcaRepo,
    PermisoRepo,
    PersonaRepo,
    RolRepo,
    SucursalRepo,
    UsuarioRepo,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared import auditoria


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
    auditoria.registrar(
        session, usuario_id=actor_id, entidad="usuario", entidad_id=usuario.id,
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


def q_usuarios(session: Session):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return UsuarioRepo(session).q_list()


# --- Persona (party model, RN-GEN-007) --------------------------------------
def crear_persona(
    session: Session,
    *,
    nombres: str,
    apellidos: str,
    tipo_documento: str,
    numero_documento: str,
    fecha_nacimiento=None,
    domicilio: str | None = None,
    telefono: str | None = None,
    email: str | None = None,
) -> Persona:
    repo = PersonaRepo(session)
    if repo.get_by_documento(numero_documento):
        raise Conflicto(f"numero_documento '{numero_documento}' ya existe")
    return repo.add(
        Persona(
            nombres=nombres,
            apellidos=apellidos,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            fecha_nacimiento=fecha_nacimiento,
            domicilio=domicilio,
            telefono=telefono,
            email=email,
        )
    )


def obtener_persona(session: Session, persona_id: uuid.UUID) -> Persona:
    return _get(PersonaRepo(session).get(persona_id), "persona")


def listar_personas(session: Session, q: str | None = None) -> list[Persona]:
    return PersonaRepo(session).list(q)


def q_personas(session: Session, q: str | None = None):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return PersonaRepo(session).q_list(q)


# --- Organización (Almacen vive acá por historia, ver data-model §1) --------
def listar_almacenes(session: Session, empresa_id: uuid.UUID | None = None) -> list[Almacen]:
    return AlmacenRepo(session).list(empresa_id)


def listar_marcas(session: Session, empresa_id: uuid.UUID | None = None) -> list[Marca]:
    return MarcaRepo(session).list(empresa_id)


def listar_sucursales(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[Sucursal]:
    return SucursalRepo(session).list(empresa_id)


def editar_persona(
    session: Session, persona_id: uuid.UUID, *, version: int, **campos
) -> Persona:
    repo = PersonaRepo(session)
    actual = _get(repo.get(persona_id), "persona")
    if actual.anonimizado_at is not None:
        raise Conflicto("persona anonimizada (Ley 29733): no admite rectificación")
    numero_nuevo = campos.get("numero_documento")
    if numero_nuevo:
        otra = repo.get_by_documento(numero_nuevo)
        if otra is not None and otra.id != persona_id:
            raise Conflicto(f"numero_documento '{numero_nuevo}' ya existe")
    actualizada = repo.actualizar_con_lock(persona_id, version, **campos)
    if actualizada is None:
        raise Conflicto(
            f"version {version} desactualizada (actual {actual.version})"
        )
    return actualizada


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


def roles_de_usuario(session: Session, usuario_id: uuid.UUID) -> list[Rol]:
    _get(UsuarioRepo(session).get(usuario_id), "usuario")
    return UsuarioRepo(session).roles_de(usuario_id)


def permisos_de_rol(session: Session, rol_id: uuid.UUID) -> list[Permiso]:
    _get(RolRepo(session).get(rol_id), "rol")
    return RolRepo(session).permisos_de(rol_id)


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
        auditoria.registrar(
            session, usuario_id=actor_id, entidad="usuario_rol", entidad_id=usuario_id,
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
        auditoria.registrar(
            session, usuario_id=actor_id, entidad="rol_permiso", entidad_id=rol_id,
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
