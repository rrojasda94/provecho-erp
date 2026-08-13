"""Routers FastAPI del módulo users: auth, perfil propio y administración."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit_login
from src.core.tenant import FueraDeAlcance, Tenant
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
    organizacion,
    privacidad,
    tokens,
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
# Aparte de `users.gestionar` en los dos sentidos: RRHH atiende el "me olvidé
# el PIN" sin tener que poder crear cuentas ni repartir roles, y administrar
# usuarios no trae de arrastre la facultad de entrar como cualquiera de ellos.
RESETEAR_PIN = "users.resetear_pin"
# Separado de `users.gestionar` a propósito: dar de alta un local o cambiar
# el RUC de la empresa no es administrar usuarios. Quien crea cajeros no
# tiene por qué poder fundar sucursales.
ORGANIZACION = "organizacion.gestionar"
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


@router.post(
    "/auth/verificar-pin",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
    dependencies=[Depends(rate_limit_login)],
)
def verificar_pin(
    body: schemas.VerificarPinIn,
    request: Request,
    actor: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Confirma que quien está frente al terminal sigue siendo el dueño de
    la sesión — desbloqueo de la pantalla del PDV (RN-POS-014).

    Detrás del mismo rate limit que el login y contra el mismo lockout: es
    otro endpoint que recibe PINes, y sin freno sería el camino cómodo
    para probarlos.
    """
    try:
        auth.verificar_pin(session, actor, body.pin, client_ip(request))
    except (CredencialesInvalidas, UsuarioBloqueado) as e:
        session.commit()  # persistir intento fallido / lockout
        raise http_exception(e) from e
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        debe_cambiar_pin=usuario.debe_cambiar_pin,
        preferencia_paleta=usuario.preferencia_paleta,
        preferencia_tamano_fuente=usuario.preferencia_tamano_fuente,
        preferencia_tema=usuario.preferencia_tema,
    )


@router.post(
    "/users/me/pin", status_code=status.HTTP_204_NO_CONTENT, tags=["users"]
)
def cambiar_pin_propio(
    body: schemas.PinPropioChange,
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """El dueño de la cuenta cambia su PIN.

    Sin permiso: elegir la propia clave no es un privilegio que alguien tenga
    que otorgar, y es la única salida de un PIN reseteado.

    Declarada **antes** que `/users/{usuario_id}/pin`: FastAPI resuelve por
    orden de declaración, y la ruta con parámetro capturaba "me" como si fuera
    un id — con lo que cambiar el PIN propio terminaba exigiendo
    `users.gestionar`.
    """
    admin.cambiar_pin_propio(
        session, usuario.id, pin_actual=body.pin_actual, nuevo_pin=body.pin_nuevo
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/users/me/preferencias", response_model=schemas.MeOut, tags=["users"])
def actualizar_preferencias(
    datos: schemas.PreferenciasIn,
    usuario: Usuario = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Cambia cómo se le presenta el ERP a quien está autenticado.

    Sin permiso: no hay privilegio que otorgar en elegir el tamaño de la
    propia letra, y exigir uno dejaría la accesibilidad fuera del alcance de
    justamente quien más la necesita. Solo puede tocar su propio perfil —el
    usuario sale del token, no del cuerpo.
    """
    if datos.paleta is not None:
        usuario.preferencia_paleta = datos.paleta
    if datos.tamano_fuente is not None:
        usuario.preferencia_tamano_fuente = datos.tamano_fuente
    if datos.tema is not None:
        usuario.preferencia_tema = datos.tema
    session.commit()
    session.refresh(usuario)

    claims = auth.build_claims(session, usuario)
    return schemas.MeOut(
        id=usuario.id,
        username=usuario.username,
        tipo=usuario.tipo,
        roles=claims["roles"],
        sucursales=claims["sucursales"],
        empresa_id=claims["empresa_id"],
        permisos=sorted(UsuarioRepo(session).permiso_codigos(usuario.id)),
        debe_cambiar_pin=usuario.debe_cambiar_pin,
        preferencia_paleta=usuario.preferencia_paleta,
        preferencia_tamano_fuente=usuario.preferencia_tamano_fuente,
        preferencia_tema=usuario.preferencia_tema,
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


@router.get("/marcas", response_model=list[schemas.MarcaOut], tags=["users"])
def listar_marcas_organizacion(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Mismo criterio que `/almacenes`: catálogo de referencia, abierto a
    cualquier autenticado pero escopado por tenant.

    Existe además de `GET /sales/marcas` porque aquel exige `sales.leer`, y
    quien arma una campaña o una pieza de contenido tiene `marketing.*`, no
    permisos de ventas — pedirle `sales.leer` para llenar un `<select>`
    sería abrirle la carta entera.
    """
    return admin.listar_marcas(session, tenant.filtro_empresa(empresa_id))


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
    "/users/{usuario_id}/pin/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def resetear_pin(
    usuario_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(RESETEAR_PIN)),
    session: Session = Depends(get_db),
):
    """Devuelve la cuenta al PIN por defecto y obliga a cambiarlo al entrar.

    Permiso propio y no `users.gestionar`: RRHH atiende el "me olvidé el PIN"
    todos los lunes y no tiene por qué poder crear cuentas ni repartir roles
    para eso. En el otro sentido, resetear el PIN de alguien es poder entrar
    como esa persona, así que tampoco viene gratis con administrar usuarios.
    """
    admin.resetear_pin(session, usuario_id, actor_id=actor.id)
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


# --- Tokens de API de agentes (`tipo=agente_ia`) -----------------------------
@router.post(
    "/users/{usuario_id}/tokens",
    response_model=schemas.TokenAgenteCreado,
    status_code=status.HTTP_201_CREATED,
    tags=["users-admin"],
)
def crear_token_agente(
    usuario_id: uuid.UUID,
    body: schemas.TokenAgenteCreate,
    actor: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    """Emite la credencial de larga vida de una cuenta de agente. El token en
    claro sale **una sola vez**: acá se guarda su SHA-256."""
    fila, raw = tokens.crear(
        session,
        usuario_id,
        nombre=body.nombre,
        dias_validez=body.dias_validez,
        actor_id=actor.id,
    )
    session.commit()
    return schemas.TokenAgenteCreado(
        **schemas.TokenAgenteOut.model_validate(fila).model_dump(), token=raw
    )


@router.get(
    "/users/{usuario_id}/tokens",
    response_model=list[schemas.TokenAgenteOut],
    tags=["users-admin"],
)
def listar_tokens_agente(
    usuario_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    return tokens.listar(session, usuario_id)


@router.delete(
    "/users/{usuario_id}/tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users-admin"],
)
def revocar_token_agente(
    usuario_id: uuid.UUID,
    token_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(GESTIONAR)),
    session: Session = Depends(get_db),
):
    tokens.revocar(session, usuario_id, token_id, actor_id=actor.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Organización: grupo, empresa, marca, sucursal, almacén ------------------
# En esta sección el superusuario (permiso `*`) opera sobre **toda** la
# organización, aunque tenga sucursales asignadas. El resto del ERP le exige
# el tenant igual que a cualquiera y está bien: una venta pertenece a una
# empresa. Acá el recurso administrado ES la empresa, y el seeder ata la
# cuenta de administración a las sucursales justamente para que el resto le
# funcione — negarle por eso el alta de la segunda empresa del grupo sería
# el mundo al revés.
def _solo_superusuario(tenant: Tenant) -> None:
    """Fundar un grupo o una empresa es un acto por encima de cualquier
    tenant: el recurso nuevo todavía no pertenece a la empresa de nadie. Un
    admin de empresa (con `organizacion.gestionar` pero sin `*`) administra
    la suya y no funda otras."""
    if not tenant.superusuario:
        raise FueraDeAlcance("operación reservada a la cuenta de administración")


def _exigir_empresa(tenant: Tenant, empresa_id: uuid.UUID) -> None:
    if tenant.superusuario:
        return
    tenant.exigir_empresa(empresa_id)


def _filtro_empresa(tenant: Tenant) -> uuid.UUID | None:
    """`None` = sin filtro. El superusuario ve el grupo entero; el resto,
    solo la empresa de su token."""
    return None if tenant.superusuario else tenant.empresa()


def _empresa_destino(tenant: Tenant, explicito: uuid.UUID | None) -> uuid.UUID:
    """`empresa_id` de un alta. Sale del token (ADR-004); el superusuario es
    el único que puede indicar una empresa distinta de la suya."""
    if tenant.superusuario:
        destino = explicito or tenant.empresa_id
        if destino is None:
            raise HTTPException(422, "empresa_id es obligatorio sin empresa en el token")
        return destino
    return tenant.empresa(explicito)


def _grupo_del_tenant(
    session: Session, tenant: Tenant, explicito: uuid.UUID | None
) -> uuid.UUID:
    """Grupo sobre el que opera quien pide. Sale de su empresa, igual que el
    `empresa_id` sale del token: la marca es del grupo, no de la empresa."""
    if explicito is not None:
        if tenant.superusuario:
            return explicito
        if explicito != _grupo_propio(session, tenant):
            raise FueraDeAlcance("grupo fuera del alcance del usuario")
        return explicito
    if tenant.empresa_id is not None:
        return _grupo_propio(session, tenant)
    _solo_superusuario(tenant)
    raise HTTPException(422, "grupo_id es obligatorio sin empresa en el token")


def _grupo_propio(session: Session, tenant: Tenant) -> uuid.UUID:
    return organizacion.obtener_empresa(session, tenant.empresa()).grupo_id


def _exigir_grupo(session: Session, tenant: Tenant, grupo_id: uuid.UUID) -> None:
    if tenant.superusuario:
        return
    if grupo_id != _grupo_propio(session, tenant):
        raise FueraDeAlcance("recurso fuera del alcance del usuario")


@router.post(
    "/grupos",
    response_model=schemas.GrupoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["organizacion"],
)
def crear_grupo(
    body: schemas.GrupoCreate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _solo_superusuario(tenant)
    grupo = organizacion.crear_grupo(session, nombre=body.nombre, actor_id=actor.id)
    session.commit()
    return grupo


@router.get("/grupos", response_model=list[schemas.GrupoOut], tags=["organizacion"])
def listar_grupos(
    _: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Quien no es superusuario ve solo el suyo. Hoy hay un único grupo y
    daría igual; el día que el ERP aloje a otro, el listado no puede ser la
    puerta por la que se entera."""
    if tenant.superusuario:
        return organizacion.listar_grupos(session)
    return [organizacion.obtener_grupo(session, _grupo_propio(session, tenant))]


@router.get(
    "/grupos/{grupo_id}", response_model=schemas.GrupoOut, tags=["organizacion"]
)
def obtener_grupo(
    grupo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    grupo = organizacion.obtener_grupo(session, grupo_id)
    _exigir_grupo(session, tenant, grupo.id)
    return grupo


@router.patch(
    "/grupos/{grupo_id}", response_model=schemas.GrupoOut, tags=["organizacion"]
)
def editar_grupo(
    grupo_id: uuid.UUID,
    body: schemas.GrupoUpdate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _solo_superusuario(tenant)
    grupo = organizacion.editar_grupo(
        session, grupo_id, nombre=body.nombre, actor_id=actor.id
    )
    session.commit()
    return grupo


@router.post(
    "/empresas",
    response_model=schemas.EmpresaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["organizacion"],
)
def crear_empresa(
    body: schemas.EmpresaCreate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _solo_superusuario(tenant)
    empresa = organizacion.crear_empresa(session, actor_id=actor.id, **body.model_dump())
    session.commit()
    return empresa


@router.get("/empresas", response_model=list[schemas.EmpresaOut], tags=["organizacion"])
def listar_empresas(
    _: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Quien no es superusuario ve solo la empresa de su token: el listado
    del grupo no es dato de un admin de local."""
    return organizacion.listar_empresas(session, _filtro_empresa(tenant))


@router.get(
    "/empresas/{empresa_id}", response_model=schemas.EmpresaOut, tags=["organizacion"]
)
def obtener_empresa(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    empresa = organizacion.obtener_empresa(session, empresa_id)
    _exigir_empresa(tenant, empresa.id)
    return empresa


@router.patch(
    "/empresas/{empresa_id}", response_model=schemas.EmpresaOut, tags=["organizacion"]
)
def editar_empresa(
    empresa_id: uuid.UUID,
    body: schemas.EmpresaUpdate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _exigir_empresa(tenant, organizacion.obtener_empresa(session, empresa_id).id)
    empresa = organizacion.editar_empresa(
        session, empresa_id, actor_id=actor.id, **body.model_dump()
    )
    session.commit()
    return empresa


@router.delete(
    "/empresas/{empresa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["organizacion"],
)
def dar_de_baja_empresa(
    empresa_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Baja **lógica**: la fila queda con `deleted_at` porque sus ventas,
    compras y comprobantes siguen existiendo. Se niega si todavía tiene
    sucursales o almacenes activos."""
    _solo_superusuario(tenant)
    organizacion.dar_de_baja_empresa(session, empresa_id, actor_id=actor.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/marcas",
    response_model=schemas.MarcaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["organizacion"],
)
def crear_marca(
    body: schemas.MarcaCreate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    grupo_id = _grupo_del_tenant(session, tenant, body.grupo_id)
    marca = organizacion.crear_marca(
        session,
        grupo_id=grupo_id,
        nombre=body.nombre,
        tipo=body.tipo,
        skins=body.skins,
        actor_id=actor.id,
    )
    session.commit()
    return marca


@router.get(
    "/marcas/{marca_id}", response_model=schemas.MarcaOut, tags=["organizacion"]
)
def obtener_marca(
    marca_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    marca = organizacion.obtener_marca(session, marca_id)
    _exigir_grupo(session, tenant, marca.grupo_id)
    return marca


@router.patch(
    "/marcas/{marca_id}", response_model=schemas.MarcaOut, tags=["organizacion"]
)
def editar_marca(
    marca_id: uuid.UUID,
    body: schemas.MarcaUpdate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _exigir_grupo(session, tenant, organizacion.obtener_marca(session, marca_id).grupo_id)
    marca = organizacion.editar_marca(
        session, marca_id, actor_id=actor.id, **body.model_dump()
    )
    session.commit()
    return marca


@router.delete(
    "/marcas/{marca_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["organizacion"]
)
def dar_de_baja_marca(
    marca_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _exigir_grupo(session, tenant, organizacion.obtener_marca(session, marca_id).grupo_id)
    organizacion.dar_de_baja_marca(session, marca_id, actor_id=actor.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/empresas/{empresa_id}/marcas",
    response_model=schemas.LicenciaMarcaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["organizacion"],
)
def otorgar_licencia_marca(
    empresa_id: uuid.UUID,
    body: schemas.LicenciaMarcaIn,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Licencia la marca a la empresa (N:N, franquicia interna). Sin esto una
    sucursal de esa marca no puede existir."""
    _exigir_empresa(tenant, empresa_id)
    licencia = organizacion.otorgar_licencia(
        session, empresa_id, body.marca_id, actor_id=actor.id
    )
    session.commit()
    return licencia


@router.get(
    "/empresas/{empresa_id}/marcas",
    response_model=list[schemas.LicenciaMarcaOut],
    tags=["organizacion"],
)
def listar_licencias_marca(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _exigir_empresa(tenant, empresa_id)
    return organizacion.listar_licencias(session, empresa_id)


@router.delete(
    "/empresas/{empresa_id}/marcas/{marca_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["organizacion"],
)
def revocar_licencia_marca(
    empresa_id: uuid.UUID,
    marca_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _exigir_empresa(tenant, empresa_id)
    organizacion.revocar_licencia(session, empresa_id, marca_id, actor_id=actor.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sucursales",
    response_model=schemas.SucursalOut,
    status_code=status.HTTP_201_CREATED,
    tags=["organizacion"],
)
def crear_sucursal(
    body: schemas.SucursalCreate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = _empresa_destino(tenant, campos.pop("empresa_id"))
    sucursal = organizacion.crear_sucursal(session, actor_id=actor.id, **campos)
    session.commit()
    return sucursal


@router.get(
    "/sucursales/{sucursal_id}",
    response_model=schemas.SucursalOut,
    tags=["organizacion"],
)
def obtener_sucursal(
    sucursal_id: uuid.UUID,
    _: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Lectura con el mismo criterio que `GET /sucursales`: catálogo de
    referencia para cualquier autenticado, escopado por tenant."""
    sucursal = organizacion.obtener_sucursal(session, sucursal_id)
    _exigir_empresa(tenant, sucursal.empresa_id)
    return sucursal


@router.patch(
    "/sucursales/{sucursal_id}",
    response_model=schemas.SucursalOut,
    tags=["organizacion"],
)
def editar_sucursal(
    sucursal_id: uuid.UUID,
    body: schemas.SucursalUpdate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cerrar un local es `estado="inactiva"` — no hay DELETE de sucursal:
    sigue siendo el ancla de sus ventas, cajas y trabajadores."""
    actual = organizacion.obtener_sucursal(session, sucursal_id)
    _exigir_empresa(tenant, actual.empresa_id)
    sucursal = organizacion.editar_sucursal(
        session, sucursal_id, actor_id=actor.id, **body.model_dump()
    )
    session.commit()
    return sucursal


@router.post(
    "/almacenes",
    response_model=schemas.AlmacenOut,
    status_code=status.HTTP_201_CREATED,
    tags=["organizacion"],
)
def crear_almacen(
    body: schemas.AlmacenCreate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = _empresa_destino(tenant, campos.pop("empresa_id"))
    almacen = organizacion.crear_almacen(session, actor_id=actor.id, **campos)
    session.commit()
    return almacen


@router.get(
    "/almacenes/{almacen_id}", response_model=schemas.AlmacenOut, tags=["organizacion"]
)
def obtener_almacen(
    almacen_id: uuid.UUID,
    _: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    almacen = organizacion.obtener_almacen(session, almacen_id)
    _exigir_empresa(tenant, almacen.empresa_id)
    return almacen


@router.patch(
    "/almacenes/{almacen_id}",
    response_model=schemas.AlmacenOut,
    tags=["organizacion"],
)
def editar_almacen(
    almacen_id: uuid.UUID,
    body: schemas.AlmacenUpdate,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _exigir_empresa(tenant, organizacion.obtener_almacen(session, almacen_id).empresa_id)
    almacen = organizacion.editar_almacen(
        session, almacen_id, actor_id=actor.id, **body.model_dump()
    )
    session.commit()
    return almacen


@router.delete(
    "/almacenes/{almacen_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["organizacion"],
)
def dar_de_baja_almacen(
    almacen_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ORGANIZACION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Baja lógica. No mira el stock: vive en `inventory` y `users` no
    importa el dominio de otro módulo. Sí niega la baja si otros almacenes
    se abastecen de este."""
    _exigir_empresa(tenant, organizacion.obtener_almacen(session, almacen_id).empresa_id)
    organizacion.dar_de_baja_almacen(session, almacen_id, actor_id=actor.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
