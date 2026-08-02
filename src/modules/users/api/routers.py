"""Routers FastAPI del módulo users: auth, perfil propio y administración."""

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit_login
from src.modules.users.api import schemas
from src.modules.users.api.deps import (
    check_permission,
    client_ip,
    get_current_user,
    get_db,
    require_permission,
)
from src.modules.users.api.error_handlers import http_exception
from src.modules.users.application import (
    admin,
    auth,
    autorizacion,
    gerencia,
    privacidad,
)
from src.modules.users.application.errors import (
    CredencialesInvalidas,
    TokenInvalido,
    UsuarioBloqueado,
)
from src.modules.users.infrastructure.models import Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo
from src.shared import parametros

router = APIRouter()

GESTIONAR = "users.gestionar"  # permiso para el CRUD administrativo
GESTIONAR_PARAMETROS = "gerencia.gestionar_parametros_empresa"  # aprobar/rechazar
ANONIMIZAR = "personas.anonimizar"  # derecho de cancelación (Ley 29733, ADR-011)


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
        raise http_exception(e) from e
    session.commit()
    return tokens


@router.post(
    "/auth/autorizar",
    response_model=schemas.AutorizacionOut,
    tags=["auth"],
    dependencies=[Depends(rate_limit_login)],
)
def autorizar(
    body: schemas.AutorizacionIn, request: Request, session: Session = Depends(get_db)
):
    """Elevación puntual de supervisor sobre el terminal de otro: verifica
    su PIN **y** que tenga el permiso, y devuelve un token de corta vida
    acotado a esa acción (RN-AUD-005).

    Va detrás del mismo rate limit que el login: es un endpoint que recibe
    PINes y sin freno sería el camino cómodo para probarlos.
    """
    try:
        resultado = autorizacion.emitir(
            session,
            username=body.username,
            pin=body.pin,
            permiso=body.permiso,
            ip=client_ip(request),
        )
    except CredencialesInvalidas as e:
        session.commit()  # persistir el rastro del intento
        raise http_exception(e) from e
    session.commit()
    return resultado


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
        raise http_exception(e) from e
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
    persona = admin.crear_persona(session, **body.model_dump())
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
    return admin.obtener_persona(session, persona_id)


@router.patch("/personas/{persona_id}", response_model=schemas.PersonaOut, tags=["personas"])
def editar_persona(
    persona_id: uuid.UUID,
    body: schemas.PersonaUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    persona = admin.editar_persona(session, persona_id, **body.model_dump())
    session.commit()
    return persona


@router.post(
    "/personas/{persona_id}/anonimizar",
    response_model=schemas.PersonaOut,
    tags=["personas"],
)


def anonimizar_persona(
    persona_id: uuid.UUID,
    body: schemas.AnonimizarPersonaIn,
    usuario: Usuario = Depends(require_permission(ANONIMIZAR)),
    session: Session = Depends(get_db),
):
    """Derecho de cancelación (Ley 29733, ADR-011): irreversible, no borra
    la fila. Verificar antes de llamar que no exista una obligación de
    retención vigente en otro módulo (trabajador activo, comprobante bajo
    retención tributaria) — el sistema no lo bloquea automáticamente."""
    persona = privacidad.anonimizar_persona(
        session,
        persona_id,
        motivo=body.motivo,
        solicitado_por=usuario.id,
    )
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
    usuario = admin.editar_usuario(session, usuario_id, **body.model_dump())
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
    admin.cambiar_pin(session, usuario_id, body.pin)
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
    admin.asignar_rol(session, usuario_id, body.rol_id, actor_id=actor.id)
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
    admin.asignar_sucursal(session, usuario_id, body.sucursal_id)
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
    rol = admin.crear_rol(session, nombre=body.nombre, descripcion=body.descripcion)
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
    admin.asignar_permiso(session, rol_id, body.permiso_id, actor_id=actor.id)
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
    permiso = admin.crear_permiso(
        session,
        codigo=body.codigo,
        descripcion=body.descripcion,
        restricciones=body.restricciones,
    )
    session.commit()
    return permiso


@router.get("/permisos", response_model=list[schemas.PermisoOut], tags=["users-admin"])
def listar_permisos(
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    return admin.listar_permisos(session)


# --- Parámetros operativos por empresa (ADR-014) ----------------------------
# Proponer: el área, desde su módulo (permiso `<modulo>.proponer_parametro`).
# Aprobar/rechazar/modificar: solo Gerencia. El valor propuesto no llega al
# módulo hasta que Gerencia lo aprueba.
@router.post(
    "/parametros",
    response_model=schemas.ParametroEmpresaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["gerencia"],
)
def proponer_parametro(
    body: schemas.ParametroPropuesta,
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    # El permiso depende del `modulo` del body, así que no puede resolverse en
    # un `Depends` — Compras no propone parámetros de RRHH.
    check_permission(session, usuario, parametros.permiso_proponer(body.modulo))
    parametro = gerencia.proponer_parametro(
        session, propuesto_por_id=usuario.id, **body.model_dump()
    )
    session.commit()
    return parametro


@router.get(
    "/parametros", response_model=list[schemas.ParametroEmpresaOut], tags=["gerencia"]
)
def listar_parametros(
    empresa_id: uuid.UUID | None = None,
    estado: str | None = None,
    modulo: str | None = None,
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """`?estado=propuesto` = bandeja de aprobaciones de Gerencia. Sin filtro de
    `modulo` hace falta el permiso de Gerencia: hay parámetros sensibles (los
    rangos salariales de RRHH) que no son de lectura general."""
    exigidos = [GESTIONAR_PARAMETROS]
    if modulo in parametros.MODULOS:
        exigidos.append(parametros.permiso_proponer(modulo))
    check_permission(session, usuario, *exigidos)
    return gerencia.listar_parametros(session, empresa_id, estado, modulo)


@router.post(
    "/parametros/{parametro_id}/aprobar",
    response_model=schemas.ParametroEmpresaOut,
    tags=["gerencia"],
)
def aprobar_parametro(
    parametro_id: uuid.UUID,
    body: schemas.ParametroAprobacion,
    usuario: Usuario = Depends(require_permission(GESTIONAR_PARAMETROS)),
    session: Session = Depends(get_db),
):
    parametro = gerencia.aprobar_parametro(
        session, parametro_id, resuelto_por_id=usuario.id, valor=body.valor
    )
    session.commit()
    return parametro


@router.post(
    "/parametros/{parametro_id}/rechazar",
    response_model=schemas.ParametroEmpresaOut,
    tags=["gerencia"],
)
def rechazar_parametro(
    parametro_id: uuid.UUID,
    body: schemas.ParametroRechazo,
    usuario: Usuario = Depends(require_permission(GESTIONAR_PARAMETROS)),
    session: Session = Depends(get_db),
):
    parametro = gerencia.rechazar_parametro(
        session,
        parametro_id,
        resuelto_por_id=usuario.id,
        motivo_rechazo=body.motivo_rechazo,
    )
    session.commit()
    return parametro
