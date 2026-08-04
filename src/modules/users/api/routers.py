"""Routers FastAPI del módulo users: auth, perfil propio y administración."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit_login
from src.core.tenant import Tenant
from src.modules.users.api import schemas
from src.modules.users.api.deps import (
    check_permission,
    client_ip,
    get_current_user,
    get_db,
    get_tenant,
    require_permission,
)
from src.modules.users.api.error_handlers import http_exception
from src.modules.users.application import (
    admin,
    auth,
    autorizacion,
    gerencia,
    notificaciones,
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
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter()

GESTIONAR = "users.gestionar"  # permiso para el CRUD administrativo
GESTIONAR_PARAMETROS = "gerencia.gestionar_parametros_empresa"  # aprobar/rechazar
# Decidir es la facultad gerencial en sí (RN-GER-002), separada de configurar
# parámetros: un gerente firma actas aunque no toque umbrales.
DECIDIR = "gerencia.decidir"
# Leer el acta es más ancho que firmarla: el área ejecutora (RN-GER-005)
# necesita ver qué se decidió y con qué condiciones, sin poder decidir.
LEER_DECISIONES = "gerencia.leer_decisiones"
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


@router.get("/personas", response_model=Pagina[schemas.PersonaOut], tags=["personas"])
def listar_personas(
    q: str | None = None,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(session, admin.q_personas(session, q), p)


@router.get(
    "/personas/buscar", response_model=list[schemas.PersonaBusquedaOut], tags=["personas"]
)
def buscar_personas(
    q: str | None = None,
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Selector de "elegir persona existente" para otro módulo (RRHH al
    contratar, Compras al dar de alta un proveedor natural). Responde con
    `PersonaBusquedaOut` — nunca la ficha completa — así que puede abrirse a
    `personas.leer` sin exponer domicilio/teléfono/email. Ruta declarada
    antes de `/personas/{persona_id}` a propósito: si quedara después,
    "buscar" se intentaría parsear como UUID y devolvería 422."""
    check_permission(session, usuario, GESTIONAR, "personas.leer")
    return admin.listar_personas(session, q)


@router.get("/almacenes", response_model=list[schemas.AlmacenOut], tags=["users"])
def listar_almacenes(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Lista de referencia (nombre/tipo de almacén, no dato sensible) — abierta
    a cualquier usuario autenticado, la necesita cualquiera que tenga que
    elegir un destino (ej. compras crea una OC). Sin `require_permission`
    a propósito: no es un recurso a proteger, es un catálogo de apoyo. Sí
    escopada por tenant — un almacén de otra empresa no es "no sensible"."""
    return admin.listar_almacenes(session, tenant.filtro_empresa(empresa_id))


@router.get(
    "/notificaciones", response_model=Pagina[schemas.NotificacionOut], tags=["users"]
)
def listar_notificaciones(
    solo_no_leidas: bool = True,
    usuario: Usuario = Depends(get_current_user),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """La bandeja del usuario autenticado. Sin `require_permission` a
    propósito: no es un recurso a proteger por rol, cada uno ve **lo suyo**
    y el filtro es la identidad, no un permiso."""
    return paginar(
        session,
        notificaciones.q_bandeja(usuario.id, solo_no_leidas=solo_no_leidas),
        p,
    )


@router.post(
    "/notificaciones/{notificacion_id}/leer",
    response_model=schemas.NotificacionOut,
    tags=["users"],
)
def leer_notificacion(
    notificacion_id: uuid.UUID,
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    fila = notificaciones.marcar_leida(session, notificacion_id, usuario.id)
    if fila is None:
        raise HTTPException(404, "Notificación no encontrada")
    session.commit()
    return fila


@router.post("/notificaciones/leer-todas", tags=["users"])
def leer_todas_las_notificaciones(
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    marcadas = notificaciones.marcar_todas_leidas(session, usuario.id)
    session.commit()
    return {"marcadas": marcadas}


@router.get("/sucursales", response_model=list[schemas.SucursalOut], tags=["users"])
def listar_sucursales(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Catálogo de referencia (nombre/estado), mismo criterio que
    `/almacenes`: cualquier autenticado que tenga que elegir una sucursal lo
    necesita — el filtro por sucursales del tablero de reportes, entre
    otros. Escopado por tenant; el RBAC real lo aplica cada endpoint que
    después use ese `sucursal_id`."""
    return admin.listar_sucursales(session, tenant.filtro_empresa(empresa_id))


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


@router.get(
    "/users/{usuario_id}/roles",
    response_model=list[schemas.RolOut],
    tags=["users-admin"],
)
def listar_roles_de_usuario(
    usuario_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    """Los roles de una cuenta, con su id — `rol_nombres` del token solo
    trae nombres y la pantalla necesita poder quitarlos."""
    return admin.roles_de_usuario(session, usuario_id)


@router.get("/users", response_model=Pagina[schemas.UsuarioOut], tags=["users-admin"])
def listar_usuarios(
    _: Usuario = Depends(require_permission(GESTIONAR)),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(session, admin.q_usuarios(session), p)


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


@router.get(
    "/roles/{rol_id}/permisos",
    response_model=list[schemas.PermisoOut],
    tags=["users-admin"],
)
def listar_permisos_de_rol(
    rol_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    """Qué habilita el rol. Asignar un rol a ciegas es exactamente el error
    que este endpoint evita."""
    return admin.permisos_de_rol(session, rol_id)


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


# --- Divisas (RN-GER-010) ----------------------------------------------------
# CRUD antes diferido (ADR-014 Addendum b): hoy solo se editaba por seeder.
@router.post(
    "/divisas",
    response_model=schemas.DivisaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["gerencia"],
)
def crear_divisa(
    body: schemas.DivisaCreate,
    _: Usuario = Depends(require_permission(GESTIONAR_PARAMETROS)),
    session: Session = Depends(get_db),
):
    divisa = gerencia.crear_divisa(session, **body.model_dump())
    session.commit()
    return divisa


@router.get("/divisas", response_model=list[schemas.DivisaOut], tags=["gerencia"])
def listar_divisas(
    _: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    # Lectura abierta a cualquier autenticado (como /almacenes): cualquier
    # módulo que declare un monto necesita poder listar divisas válidas.
    return gerencia.listar_divisas(session)


@router.patch("/divisas/{divisa_id}", response_model=schemas.DivisaOut, tags=["gerencia"])
def editar_divisa(
    divisa_id: uuid.UUID,
    body: schemas.DivisaUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR_PARAMETROS)),
    session: Session = Depends(get_db),
):
    divisa = gerencia.editar_divisa(session, divisa_id, **body.model_dump())
    session.commit()
    return divisa


# --- Acta de decisión gerencial (RN-GER-002) --------------------------------
@router.post(
    "/decisiones-gerenciales",
    response_model=schemas.DecisionGerencialOut,
    status_code=status.HTTP_201_CREATED,
    tags=["gerencia"],
)
def registrar_decision_gerencial(
    body: schemas.DecisionGerencialCreate,
    usuario: Usuario = Depends(require_permission(DECIDIR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Materializa el acta de una decisión gerencial: una decisión verbal no
    tiene validez operativa (RN-GER-002). `decidido_por_id` sale del token,
    nunca del cuerpo — atribuirle la decisión a otro gerente invalidaría el
    acta entera."""
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos.pop("empresa_id"))
    decision = gerencia.registrar_decision(
        session, decidido_por_id=usuario.id, **campos
    )
    session.commit()
    return decision


@router.get(
    "/decisiones-gerenciales",
    response_model=list[schemas.DecisionGerencialOut],
    tags=["gerencia"],
)
def listar_decisiones_gerenciales(
    empresa_id: uuid.UUID | None = None,
    referencia_tipo: str | None = None,
    referencia_id: uuid.UUID | None = None,
    tipo: str | None = None,
    _: Usuario = Depends(require_permission(LEER_DECISIONES)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El acceso típico es `?referencia_tipo=orden_compra&referencia_id=...`:
    "qué decidió Gerencia sobre esto", desde el módulo que lo tiene en
    pantalla."""
    return gerencia.listar_decisiones(
        session,
        tenant.filtro_empresa(empresa_id),
        referencia_tipo,
        referencia_id,
        tipo,
    )


@router.get(
    "/decisiones-gerenciales/{decision_id}",
    response_model=schemas.DecisionGerencialOut,
    tags=["gerencia"],
)
def ver_decision_gerencial(
    decision_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER_DECISIONES)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    decision = gerencia.obtener_decision(session, decision_id)
    tenant.exigir_empresa(decision.empresa_id)
    return decision
