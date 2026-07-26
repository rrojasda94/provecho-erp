"""Routers FastAPI del módulo users: auth, perfil propio y administración."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit_login
from src.modules.users.api import schemas
from src.modules.users.api.deps import (
    client_ip,
    get_current_user,
    get_db,
    require_permission,
)
from src.modules.users.application import admin, auth, gerencia
from src.modules.users.application.errors import (
    Conflicto,
    CredencialesInvalidas,
    NoEncontrado,
    PinInvalido,
    TokenInvalido,
    UsersError,
    UsuarioBloqueado,
)
from src.modules.users.infrastructure.models import Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo

router = APIRouter()

GESTIONAR = "users.gestionar"  # permiso para el CRUD administrativo
GESTIONAR_REGLAS = "gerencia.gestionar_reglas_aprobacion"

_HTTP_STATUS: dict[type[UsersError], int] = {
    CredencialesInvalidas: status.HTTP_401_UNAUTHORIZED,
    TokenInvalido: status.HTTP_401_UNAUTHORIZED,
    UsuarioBloqueado: status.HTTP_423_LOCKED,
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    PinInvalido: 422,
}


def _http(err: UsersError) -> HTTPException:
    return HTTPException(_HTTP_STATUS.get(type(err), 400), str(err))


# --- Auth -------------------------------------------------------------------
@router.post(
    "/auth/login",
    response_model=schemas.TokenPair,
    tags=["auth"],
    dependencies=[Depends(rate_limit_login)],
)
def login(body: schemas.LoginIn, request: Request, session: Session = Depends(get_db)):
    try:
        tokens = auth.login(session, body.username, body.pin, client_ip(request))
    except (CredencialesInvalidas, UsuarioBloqueado) as e:
        session.commit()  # persistir intento fallido / lockout
        raise _http(e) from e
    session.commit()
    return tokens


@router.post(
    "/auth/refresh",
    response_model=schemas.TokenPair,
    tags=["auth"],
    dependencies=[Depends(rate_limit_login)],
)
def refresh(body: schemas.RefreshIn, session: Session = Depends(get_db)):
    try:
        tokens = auth.refresh(session, body.refresh_token)
    except TokenInvalido as e:
        session.commit()  # persistir revocación de cadena ante reuso
        raise _http(e) from e
    session.commit()
    return tokens


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(body: schemas.RefreshIn, session: Session = Depends(get_db)):
    auth.logout(session, body.refresh_token)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/me", response_model=schemas.MeOut, tags=["users"])
def me(
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    claims = auth.build_claims(session, usuario)
    return schemas.MeOut(
        id=usuario.id,
        username=usuario.username,
        tipo=usuario.tipo,
        roles=claims["roles"],
        sucursales=claims["sucursales"],
        empresa_id=claims["empresa_id"],
        permisos=sorted(UsuarioRepo(session).permiso_codigos(usuario.id)),
    )


# --- Persona (party model) ---------------------------------------------------
@router.post(
    "/personas",
    response_model=schemas.PersonaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["personas"],
)
def crear_persona(
    body: schemas.PersonaCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        persona = admin.crear_persona(session, **body.model_dump())
    except Conflicto as e:
        raise _http(e) from e
    session.commit()
    return persona


@router.get("/personas", response_model=list[schemas.PersonaOut], tags=["personas"])
def listar_personas(
    q: str | None = None,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    return admin.listar_personas(session, q)


@router.get("/personas/{persona_id}", response_model=schemas.PersonaOut, tags=["personas"])
def obtener_persona(
    persona_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        return admin.obtener_persona(session, persona_id)
    except NoEncontrado as e:
        raise _http(e) from e


@router.patch("/personas/{persona_id}", response_model=schemas.PersonaOut, tags=["personas"])
def editar_persona(
    persona_id: uuid.UUID,
    body: schemas.PersonaUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        persona = admin.editar_persona(session, persona_id, **body.model_dump())
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return persona


# --- Administración (CRUD) --------------------------------------------------
@router.post(
    "/users",
    response_model=schemas.UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    tags=["users-admin"],
)
def crear_usuario(
    body: schemas.UsuarioCreate,
    actor: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        usuario = admin.crear_usuario(
            session,
            username=body.username,
            pin=body.pin,
            tipo=body.tipo,
            persona_id=body.persona_id,
            nombre_display=body.nombre_display,
            email=body.email,
            actor_id=actor.id,
        )
    except (Conflicto, PinInvalido) as e:
        raise _http(e) from e
    session.commit()
    return usuario


@router.get("/users", response_model=list[schemas.UsuarioOut], tags=["users-admin"])
def listar_usuarios(
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    return admin.listar_usuarios(session)


@router.patch(
    "/users/{usuario_id}", response_model=schemas.UsuarioOut, tags=["users-admin"]
)
def editar_usuario(
    usuario_id: uuid.UUID,
    body: schemas.UsuarioUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        usuario = admin.editar_usuario(session, usuario_id, **body.model_dump())
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return usuario


@router.post(
    "/users/{usuario_id}/pin",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def cambiar_pin(
    usuario_id: uuid.UUID,
    body: schemas.PinChange,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        admin.cambiar_pin(session, usuario_id, body.pin)
    except (NoEncontrado, PinInvalido) as e:
        raise _http(e) from e
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{usuario_id}/roles",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def asignar_rol(
    usuario_id: uuid.UUID,
    body: schemas.RolIdIn,
    actor: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        admin.asignar_rol(session, usuario_id, body.rol_id, actor_id=actor.id)
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/users/{usuario_id}/roles/{rol_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def quitar_rol(
    usuario_id: uuid.UUID,
    rol_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    admin.quitar_rol(session, usuario_id, rol_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{usuario_id}/sucursales",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def asignar_sucursal(
    usuario_id: uuid.UUID,
    body: schemas.SucursalIdIn,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        admin.asignar_sucursal(session, usuario_id, body.sucursal_id)
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/users/{usuario_id}/sucursales/{sucursal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def quitar_sucursal(
    usuario_id: uuid.UUID,
    sucursal_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    admin.quitar_sucursal(session, usuario_id, sucursal_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Roles ------------------------------------------------------------------
@router.post(
    "/roles",
    response_model=schemas.RolOut,
    status_code=status.HTTP_201_CREATED,
    tags=["users-admin"],
)
def crear_rol(
    body: schemas.RolCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        rol = admin.crear_rol(session, nombre=body.nombre, descripcion=body.descripcion)
    except Conflicto as e:
        raise _http(e) from e
    session.commit()
    return rol


@router.get("/roles", response_model=list[schemas.RolOut], tags=["users-admin"])
def listar_roles(
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    return admin.listar_roles(session)


@router.post(
    "/roles/{rol_id}/permisos",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def asignar_permiso(
    rol_id: uuid.UUID,
    body: schemas.PermisoIdIn,
    actor: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        admin.asignar_permiso(session, rol_id, body.permiso_id, actor_id=actor.id)
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/roles/{rol_id}/permisos/{permiso_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def quitar_permiso(
    rol_id: uuid.UUID,
    permiso_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    admin.quitar_permiso(session, rol_id, permiso_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Permisos ---------------------------------------------------------------
@router.post(
    "/permisos",
    response_model=schemas.PermisoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["users-admin"],
)
def crear_permiso(
    body: schemas.PermisoCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    try:
        permiso = admin.crear_permiso(
            session,
            codigo=body.codigo,
            descripcion=body.descripcion,
            restricciones=body.restricciones,
        )
    except Conflicto as e:
        raise _http(e) from e
    session.commit()
    return permiso


@router.get("/permisos", response_model=list[schemas.PermisoOut], tags=["users-admin"])
def listar_permisos(
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    return admin.listar_permisos(session)


# --- Reglas de aprobación (matriz de aprobaciones) --------------------------
@router.post(
    "/reglas-aprobacion",
    response_model=schemas.ReglaAprobacionOut,
    status_code=status.HTTP_201_CREATED,
    tags=["gerencia"],
)
def crear_regla_aprobacion(
    body: schemas.ReglaAprobacionCreate,
    _: Usuario = Depends(require_permission(GESTIONAR_REGLAS)),
    session: Session = Depends(get_db),
):
    try:
        regla = gerencia.crear_regla(session, **body.model_dump())
    except Conflicto as e:
        raise _http(e) from e
    session.commit()
    return regla


@router.get(
    "/reglas-aprobacion", response_model=list[schemas.ReglaAprobacionOut], tags=["gerencia"]
)
def listar_reglas_aprobacion(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(GESTIONAR_REGLAS)),
    session: Session = Depends(get_db),
):
    return gerencia.listar_reglas(session, empresa_id)


@router.patch(
    "/reglas-aprobacion/{regla_id}",
    response_model=schemas.ReglaAprobacionOut,
    tags=["gerencia"],
)
def editar_regla_aprobacion(
    regla_id: uuid.UUID,
    body: schemas.ReglaAprobacionUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR_REGLAS)),
    session: Session = Depends(get_db),
):
    try:
        regla = gerencia.editar_regla(session, regla_id, **body.model_dump())
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return regla
