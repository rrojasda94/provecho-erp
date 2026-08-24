"""Casos de uso de administración (solo admin): CRUD de usuarios, roles,
permisos y asignaciones. Los cambios de roles/permisos se auditan."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
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
    RefreshTokenRepo,
    RolRepo,
    SucursalRepo,
    UsuarioRepo,
)
from src.modules.users.infrastructure.security import hash_pin, verify_pin
from src.shared import auditoria
from src.shared.ubicacion import desanclar


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


def resetear_pin(
    session: Session, usuario_id: uuid.UUID, *, actor_id: uuid.UUID | None = None
) -> Usuario:
    """Devuelve la cuenta al PIN por defecto para que su dueño vuelva a
    entrar, y la marca para que lo primero que haga sea cambiarlo.

    Un PIN olvidado no se puede recuperar —está hasheado con Argon2id— así
    que la única salida es ponerle uno conocido. Eso deja, por un rato, una
    cuenta cuyo PIN sabe alguien más: de ahí las tres cosas que pasan juntas
    y no por separado.

    1. `debe_cambiar_pin` bloquea todo salvo cambiarlo (`api.deps`). Sin esto
       el PIN público queda vigente indefinidamente.
    2. Se **revocan los refresh tokens**: si alguien ya estaba dentro con esa
       cuenta, el reseteo lo saca. Un reseteo que deja viva la sesión anterior
       no sirve para el caso en que se hace por sospecha.
    3. Se **desbloquea el lockout**: quien olvidó su PIN normalmente lo agotó
       intentando, y dejarlo bloqueado convierte el reseteo en nada.

    Queda auditado quién reseteó a quién: es la contracara de que un
    administrador pueda entrar como cualquiera.
    """
    usuario = _get(UsuarioRepo(session).get(usuario_id), "usuario")
    if usuario.tipo != "humano":
        raise Conflicto(
            "una cuenta de agente no tiene PIN: se le rota el token (ADR-032)"
        )
    usuario.pin_hash = hash_pin(rules.PIN_POR_DEFECTO)
    usuario.debe_cambiar_pin = True
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    RefreshTokenRepo(session).revocar_usuario(usuario.id)
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="usuario",
        entidad_id=usuario.id,
        accion="resetear_pin",
        datos_despues={"username": usuario.username, "debe_cambiar_pin": True},
    )
    return usuario


def cambiar_pin_propio(
    session: Session, usuario_id: uuid.UUID, *, pin_actual: str, nuevo_pin: str
) -> Usuario:
    """Autoservicio: el dueño de la cuenta cambia su PIN con el que tiene.

    Exige el PIN actual aunque haya sesión válida: un token robado o una
    pantalla que quedó abierta no deberían alcanzar para quedarse con la
    cuenta. Y rechaza el PIN por defecto como valor nuevo — cambiarlo por el
    mismo que puso el reseteo es no cambiarlo.
    """
    usuario = _get(UsuarioRepo(session).get(usuario_id), "usuario")
    if not verify_pin(usuario.pin_hash, pin_actual):
        raise PinInvalido("El PIN actual no coincide")
    if not rules.pin_valido(nuevo_pin):
        raise PinInvalido(f"El PIN debe ser {rules.PIN_LENGTH} dígitos")
    if nuevo_pin == rules.PIN_POR_DEFECTO:
        raise PinInvalido("Elige un PIN distinto del que viene por defecto")
    usuario.pin_hash = hash_pin(nuevo_pin)
    usuario.debe_cambiar_pin = False
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
    ubicacion_place_id: str | None = None,
    ubicacion_lat: Decimal | None = None,
    ubicacion_lng: Decimal | None = None,
    ubicacion_plus_code: str | None = None,
    ubicacion_distrito: str | None = None,
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
            ubicacion_place_id=ubicacion_place_id,
            ubicacion_lat=ubicacion_lat,
            ubicacion_lng=ubicacion_lng,
            ubicacion_plus_code=ubicacion_plus_code,
            ubicacion_distrito=ubicacion_distrito,
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
    # Corregir el domicilio sin volver a elegirlo en el mapa desancla el
    # punto viejo, que ya no es de esa dirección. El borrado va DESPUÉS del
    # UPDATE y no dentro de `campos`: `actualizar_con_lock` descarta los
    # `None` —así es como distingue "no tocar"— y un `None` acá no llegaría
    # nunca a la base.
    domicilio_nuevo = campos.get("domicilio")
    desancla = (
        domicilio_nuevo is not None
        and domicilio_nuevo != actual.domicilio
        and not campos.get("ubicacion_place_id")
    )
    actualizada = repo.actualizar_con_lock(persona_id, version, **campos)
    if actualizada is None:
        raise Conflicto(
            f"version {version} desactualizada (actual {actual.version})"
        )
    if desancla:
        desanclar(actualizada)
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


def sucursales_de_usuario(session: Session, usuario_id: uuid.UUID) -> list[Sucursal]:
    _get(UsuarioRepo(session).get(usuario_id), "usuario")
    return UsuarioRepo(session).sucursales_de(usuario_id)


def asignar_sucursal(
    session: Session,
    usuario_id: uuid.UUID,
    sucursal_id: uuid.UUID,
    tenant: Tenant,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Suma un local al alcance de la cuenta.

    Un supervisor sobre varios locales son varias filas acá: `usuario_sucursal`
    ya es N a N y no hace falta agrupar nada (ADR-061).

    El alcance viaja en el token, así que el cambio recién le aplica a esa
    persona cuando su sesión renueve (refresh o login)."""
    _get(UsuarioRepo(session).get(usuario_id), "usuario")
    sucursal = _get(SucursalRepo(session).get(sucursal_id), "sucursal")
    _exigir_empresa(tenant, sucursal.empresa_id)
    if session.get(UsuarioSucursal, (usuario_id, sucursal_id)) is None:
        session.add(
            UsuarioSucursal(usuario_id=usuario_id, sucursal_id=sucursal_id)
        )
        auditoria.registrar(
            session, usuario_id=actor_id, entidad="usuario_sucursal",
            entidad_id=usuario_id, accion="asignar_sucursal",
            datos_despues={"sucursal_id": str(sucursal_id)},
        )


def quitar_sucursal(
    session: Session,
    usuario_id: uuid.UUID,
    sucursal_id: uuid.UUID,
    tenant: Tenant,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Quitar alcance también se audita: es la mitad de la pregunta "quién
    podía ver esto y desde cuándo", y sin el rastro la respuesta se pierde."""
    sucursal = _get(SucursalRepo(session).get(sucursal_id), "sucursal")
    _exigir_empresa(tenant, sucursal.empresa_id)
    fila = session.get(UsuarioSucursal, (usuario_id, sucursal_id))
    if fila is not None:
        session.delete(fila)
        auditoria.registrar(
            session, usuario_id=actor_id, entidad="usuario_sucursal",
            entidad_id=usuario_id, accion="quitar_sucursal",
            datos_antes={"sucursal_id": str(sucursal_id)},
        )


def _exigir_empresa(tenant: Tenant, empresa_id: uuid.UUID) -> None:
    """Sin esto se podía ampliar el alcance de una cuenta a la sucursal de otra
    empresa del grupo: repartir acceso a datos ajenos desde la pantalla de
    administración de la propia empresa.

    El superusuario queda afuera por el mismo motivo que en el alta de
    sucursales (`routers._exigir_empresa`): administra el grupo entero y el
    seeder lo ata a una empresa solo para que el resto del ERP le funcione."""
    if tenant.superusuario:
        return
    tenant.exigir_empresa(empresa_id)


def _get(obj, nombre: str):
    if obj is None:
        raise NoEncontrado(f"{nombre} no encontrado")
    return obj
