"""API de `reports`: catálogo, matriz de distribución, gobierno y lectura.

**No hay `POST /emitidos`.** El reporte lo emite el evento, no un cliente —
mismo criterio que ADR-031 para `audit_log`: un endpoint de escritura le
permitiría al reportado dictar lo que dice su reporte.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import destinos
from src.core.tenant import Tenant
from src.modules.reports.api import schemas
from src.modules.reports.application import areas as areas_uc
from src.modules.reports.application import destinatarios as resolucion
from src.modules.reports.application import escalamientos
from src.modules.reports.application import matriz as matriz_uc
from src.modules.reports.application import reglas as reglas_uc
from src.modules.reports.application.scope import (
    exigir_area,
    exigir_escalamiento,
    exigir_miembro,
    exigir_regla,
    exigir_reporte,
)
from src.modules.reports.domain import catalogo
from src.modules.reports.infrastructure.repositories import (
    EscalamientoRepo,
    ReglaRepo,
    ReporteEmitidoRepo,
)
from src.modules.users.api.deps import (
    client_ip,
    get_db_reportes,
    get_tenant,
    require_permission,
)
from src.modules.users.application.queries_publicas import permisos_de
from src.modules.users.infrastructure.models import Usuario
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/reports", tags=["reports"])

LEER = "reports.leer"
LEER_TODO = "reports.leer_todo"
LEER_MATRIZ = "reports.leer_matriz"
ADMINISTRAR = "reports.administrar"
# Elevar y resolver son permisos distintos a propósito: quien atiende puede
# escalar lo que no le corresponde, y quien responde por el nivel es el que
# cierra. Mismo criterio de segregación que solicitar/aprobar un ajuste.
ESCALAR = "reports.escalar"
RESOLVER = "reports.escalamiento_resolver"


def _permisos(session: Session, usuario: Usuario) -> set[str]:
    return permisos_de(session, usuario.id)


def _nombres_de(session: Session, ids) -> dict[uuid.UUID, str]:
    """`{usuario_id: username}` en una consulta. Los ids que ya no existen
    quedan fuera y cada llamador decide cómo los nombra."""
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return dict(
        session.execute(
            select(Usuario.id, Usuario.username).where(Usuario.id.in_(ids))
        ).all()
    )


def _a_salida_reporte(reporte, nombres: dict[uuid.UUID, str]):
    salida = schemas.ReporteEmitidoOut.model_validate(reporte, from_attributes=True)
    salida.actor = _nombre_actor(reporte.actor_id, nombres)
    salida.referencia_url = destinos.url(
        reporte.referencia_tipo, reporte.referencia_id
    )
    return salida


def _nombre_actor(actor_id, nombres: dict[uuid.UUID, str]) -> str:
    """Nulo es «Sistema» (RN-REP-009); un id que ya no resuelve es un usuario
    borrado, y decir «Sistema» ahí borraría al responsable del hecho."""
    if actor_id is None:
        return schemas.ACTOR_SISTEMA
    return nombres.get(actor_id, "(borrado)")


def _pagina_con_actores(session: Session, pagina: dict) -> dict:
    """Resuelve el nombre del actor de toda la página en una sola consulta."""
    nombres = _nombres_de(session, (r.actor_id for r in pagina["items"]))
    pagina["items"] = [_a_salida_reporte(r, nombres) for r in pagina["items"]]
    return pagina


def _emision_visible(session: Session, usuario: Usuario, codigo: str) -> bool:
    """La segunda puerta de RN-REP-002: el permiso del módulo dueño.

    Ser destinatario no alcanza. Alguien puede estar en el área Gerencia y no
    tener `accounting.leer`: recibe el aviso de que hubo un descuadre, no el
    detalle de la caja.
    """
    return any(
        e.codigo == codigo for e in catalogo.visibles(_permisos(session, usuario))
    )


# --- Catálogo -----------------------------------------------------------------
@router.get("/emisiones", response_model=schemas.CatalogoEmisionesOut)
def listar_emisiones(
    usuario: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db_reportes),
):
    """Solo lo que este usuario puede ver: el catálogo es una lista de
    capacidades y mostrar lo que después daría 403 solo confunde."""
    return schemas.CatalogoEmisionesOut(
        emisiones=[
            schemas.EmisionOut(
                codigo=e.codigo,
                nombre=e.nombre,
                descripcion=e.descripcion,
                permiso=e.permiso,
                nivel=e.nivel,
                ambito=e.ambito,
                campos=list(e.campos),
                areas_sugeridas=list(e.areas_sugeridas),
                dinamicos_sugeridos=list(e.dinamicos_sugeridos),
                referencia_tipo=e.referencia_tipo,
            )
            for e in catalogo.visibles(_permisos(session, usuario))
        ],
        niveles=list(catalogo.NIVELES),
        dinamicos=list(catalogo.DINAMICOS),
        destinos={
            tipo: schemas.DestinoOut(
                ruta=destinos.PREFIJO_API + d.ruta,
                permiso=d.permiso,
                etiqueta=d.etiqueta,
            )
            for tipo, d in destinos.DESTINOS.items()
        },
    )


@router.get("/matriz", response_model=list[schemas.MatrizFilaOut])
def matriz(
    usuario: Usuario = Depends(require_permission(LEER_MATRIZ)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
):
    """El mapa completo de distribución, con sus huecos y sus fugas.

    Permiso propio y no `reports.leer`: la matriz revela la estructura
    organizacional —quién responde por qué local, quién compone Gerencia— y
    eso es más de lo que necesita quien solo viene a leer sus reportes.
    """
    return matriz_uc.construir(
        session,
        empresa_id=tenant.filtro_empresa(),
        permisos=_permisos(session, usuario),
    )


# --- Áreas --------------------------------------------------------------------
@router.get("/areas", response_model=list[schemas.AreaOut])
def listar_areas(
    _: Usuario = Depends(require_permission(LEER_MATRIZ)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
):
    from src.modules.reports.infrastructure.repositories import AreaRepo

    return AreaRepo(session).list(tenant.filtro_empresa())


@router.post("/areas", response_model=schemas.AreaOut, status_code=201)
def crear_area(
    body: schemas.AreaCreate,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    area = areas_uc.crear_area(
        session,
        empresa_id=tenant.empresa(body.empresa_id),
        codigo=body.codigo,
        nombre=body.nombre,
        actor_id=actor.id,
        ip=ip,
    )
    session.commit()
    return area


@router.patch("/areas/{area_id}", response_model=schemas.AreaOut)
def editar_area(
    area_id: uuid.UUID,
    body: schemas.AreaUpdate,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    exigir_area(session, area_id, tenant)
    area = areas_uc.editar_area(
        session,
        area_id,
        nombre=body.nombre,
        activa=body.activa,
        actor_id=actor.id,
        ip=ip,
    )
    session.commit()
    return area


@router.delete("/areas/{area_id}", status_code=204)
def borrar_area(
    area_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    exigir_area(session, area_id, tenant)
    areas_uc.borrar_area(session, area_id, actor_id=actor.id, ip=ip)
    session.commit()


@router.get("/areas/{area_id}/miembros", response_model=list[schemas.MiembroOut])
def listar_miembros(
    area_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER_MATRIZ)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
):
    from src.modules.reports.infrastructure.repositories import AreaRepo

    exigir_area(session, area_id, tenant)
    return AreaRepo(session).miembros(area_id)


@router.post(
    "/areas/{area_id}/miembros", response_model=schemas.MiembroOut, status_code=201
)
def agregar_miembro(
    area_id: uuid.UUID,
    body: schemas.MiembroCreate,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    exigir_area(session, area_id, tenant)
    if body.sucursal_id is not None:
        tenant.exigir_sucursal(body.sucursal_id)
    miembro = areas_uc.agregar_miembro(
        session,
        area_id,
        rol_id=body.rol_id,
        usuario_id=body.usuario_id,
        sucursal_id=body.sucursal_id,
        actor_id=actor.id,
        ip=ip,
    )
    session.commit()
    return miembro


@router.delete("/areas/{area_id}/miembros/{miembro_id}", status_code=204)
def quitar_miembro(
    area_id: uuid.UUID,
    miembro_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    miembro = exigir_miembro(session, miembro_id, tenant)
    if miembro.area_id != area_id:
        raise HTTPException(404, "Miembro no encontrado")
    areas_uc.quitar_miembro(session, miembro_id, actor_id=actor.id, ip=ip)
    session.commit()


# --- Reglas -------------------------------------------------------------------
def _a_salida_regla(session: Session, regla) -> schemas.ReglaOut:
    salida = schemas.ReglaOut.model_validate(regla)
    salida.destinatarios = [
        schemas.DestinatarioOut.model_validate(d)
        for d in ReglaRepo(session).destinatarios(regla.id)
    ]
    return salida


@router.get("/reglas", response_model=list[schemas.ReglaOut])
def listar_reglas(
    codigo_emision: str | None = None,
    _: Usuario = Depends(require_permission(LEER_MATRIZ)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
):
    repo = ReglaRepo(session)
    reglas = list(
        session.scalars(repo.q_list(tenant.filtro_empresa(), codigo_emision))
    )
    return [_a_salida_regla(session, r) for r in reglas]


@router.post("/reglas", response_model=schemas.ReglaOut, status_code=201)
def crear_regla(
    body: schemas.ReglaCreate,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    if body.sucursal_id is not None:
        tenant.exigir_sucursal(body.sucursal_id)
    regla = reglas_uc.crear_regla(
        session,
        empresa_id=tenant.empresa(body.empresa_id),
        codigo_emision=body.codigo_emision,
        sucursal_id=body.sucursal_id,
        nivel=body.nivel,
        canal=body.canal,
        activa=body.activa,
        destinatarios=[
            reglas_uc.DestinatarioIn(**d.model_dump()) for d in body.destinatarios
        ],
        actor_id=actor.id,
        ip=ip,
    )
    session.commit()
    return _a_salida_regla(session, regla)


@router.patch("/reglas/{regla_id}", response_model=schemas.ReglaOut)
def editar_regla(
    regla_id: uuid.UUID,
    body: schemas.ReglaUpdate,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    exigir_regla(session, regla_id, tenant)
    regla = reglas_uc.editar_regla(
        session,
        regla_id,
        nivel=body.nivel,
        canal=body.canal,
        activa=body.activa,
        destinatarios=(
            [reglas_uc.DestinatarioIn(**d.model_dump()) for d in body.destinatarios]
            if body.destinatarios is not None
            else None
        ),
        actor_id=actor.id,
        ip=ip,
    )
    session.commit()
    return _a_salida_regla(session, regla)


@router.delete("/reglas/{regla_id}", status_code=204)
def borrar_regla(
    regla_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    exigir_regla(session, regla_id, tenant)
    reglas_uc.borrar_regla(session, regla_id, actor_id=actor.id, ip=ip)
    session.commit()


# --- Reportes emitidos --------------------------------------------------------
@router.get("/mios", response_model=Pagina[schemas.ReporteEmitidoOut])
def mis_reportes(
    usuario: Usuario = Depends(require_permission(LEER)),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db_reportes),
):
    """Lo que me fue entregado. Sin filtro de tenant explícito: la entrega ya
    es a mi `usuario_id`, y nadie me entrega reportes de otra empresa."""
    return _pagina_con_actores(
        session, paginar(session, ReporteEmitidoRepo(session).q_mios(usuario.id), p)
    )


@router.get("/emitidos", response_model=Pagina[schemas.ReporteEmitidoOut])
def listar_emitidos(
    codigo_emision: str | None = None,
    _: Usuario = Depends(require_permission(LEER_TODO)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db_reportes),
):
    return _pagina_con_actores(
        session,
        paginar(
            session,
            ReporteEmitidoRepo(session).q_list(
                tenant.filtro_empresa(), codigo_emision=codigo_emision
            ),
            p,
        ),
    )


def _exigir_puerta_doble(
    session: Session, reporte_id: uuid.UUID, usuario: Usuario, tenant: Tenant
):
    """RN-REP-002 en una sola función: alcance y contenido.

    1. **Alcance**: ser destinatario, o tener `reports.leer_todo`. Si no, el
       mismo 404 que si no existiera — la respuesta no confirma un reporte
       ajeno.
    2. **Contenido**: el permiso que la emisión declara, que es el de su
       módulo dueño. Estar en la lista de distribución no otorga acceso al
       dato.
    """
    reporte = exigir_reporte(session, reporte_id, tenant)
    permisos = _permisos(session, usuario)
    alcanza = "*" in permisos or LEER_TODO in permisos
    if not alcanza and not ReporteEmitidoRepo(session).es_destinatario(
        reporte_id, usuario.id
    ):
        raise HTTPException(404, "Reporte no encontrado")
    if not _emision_visible(session, usuario, reporte.codigo_emision):
        raise HTTPException(403, "Permiso denegado")
    return reporte


def _a_salida_escalamiento(
    session: Session, fila, *, con_destinatarios: bool = False
) -> schemas.EscalamientoDetalleOut:
    salida = schemas.EscalamientoDetalleOut.model_validate(fila, from_attributes=True)
    salida.acciones = list(fila.acciones or [])
    if con_destinatarios:
        ids = resolucion.del_nivel(
            session,
            fila.nivel_actual,
            empresa_id=fila.empresa_id,
            sucursal_id=fila.sucursal_id,
        )
        nombres = _nombres_de(session, ids)
        salida.destinatarios = [nombres.get(i, "(borrado)") for i in ids]
    return salida


@router.get("/escalamientos", response_model=Pagina[schemas.EscalamientoOut])
def listar_escalamientos(
    estado: str | None = None,
    nivel_actual: str | None = None,
    motivo: str | None = None,
    origen: str | None = None,
    _: Usuario = Depends(require_permission(LEER_TODO)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db_reportes),
):
    """La bandeja del que responde: qué está abierto y en qué nivel."""
    return paginar(
        session,
        EscalamientoRepo(session).q_list(
            tenant.filtro_empresa(),
            estado=estado,
            nivel_actual=nivel_actual,
            motivo=motivo,
            origen=origen,
        ),
        p,
    )


@router.get(
    "/escalamientos/{escalamiento_id}",
    response_model=schemas.EscalamientoDetalleOut,
)
def detalle_escalamiento(
    escalamiento_id: uuid.UUID,
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
):
    fila = exigir_escalamiento(session, escalamiento_id, tenant)
    # La misma doble puerta que el reporte de origen: el escalamiento cuenta
    # lo mismo que el hecho que lo provocó.
    _exigir_puerta_doble(session, fila.reporte_emitido_id, usuario, tenant)
    return _a_salida_escalamiento(session, fila, con_destinatarios=True)


@router.post(
    "/emitidos/{reporte_id}/escalamientos",
    response_model=schemas.EscalamientoDetalleOut,
    status_code=201,
)
def abrir_escalamiento(
    reporte_id: uuid.UUID,
    body: schemas.EscalamientoCreate,
    actor: Usuario = Depends(require_permission(ESCALAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    """Elevar un reporte que no se pudo resolver donde llegó (RN-CTP-004).

    Arranca siempre en `supervisor`: la cadena sube de a un escalón para que
    quede registrado quién intentó qué.
    """
    reporte = _exigir_puerta_doble(session, reporte_id, actor, tenant)
    fila = escalamientos.abrir(
        session,
        reporte,
        motivo=body.motivo,
        descripcion=body.descripcion,
        reportado_por=actor.id,
        evidencia_id=body.evidencia_id,
        ip=ip,
    )
    salida = _a_salida_escalamiento(session, fila, con_destinatarios=True)
    session.commit()
    return salida


@router.get(
    "/emitidos/{reporte_id}/escalamientos",
    response_model=list[schemas.EscalamientoDetalleOut],
)
def escalamientos_del_reporte(
    reporte_id: uuid.UUID,
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
):
    """El historial completo, no solo la cadena viva: un problema que vuelve
    a pasar es exactamente lo que la mejora continua viene a mirar."""
    _exigir_puerta_doble(session, reporte_id, usuario, tenant)
    return [
        _a_salida_escalamiento(session, fila)
        for fila in EscalamientoRepo(session).de_reporte(reporte_id)
    ]


@router.post(
    "/escalamientos/{escalamiento_id}/acciones",
    response_model=schemas.EscalamientoDetalleOut,
)
def registrar_accion(
    escalamiento_id: uuid.UUID,
    body: schemas.AccionEscalamientoIn,
    actor: Usuario = Depends(require_permission(RESOLVER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    """Qué hizo este nivel, sin cerrar ni elevar."""
    fila = exigir_escalamiento(session, escalamiento_id, tenant)
    _exigir_puerta_doble(session, fila.reporte_emitido_id, actor, tenant)
    escalamientos.registrar_accion(
        session, fila, descripcion=body.descripcion, usuario_id=actor.id, ip=ip
    )
    salida = _a_salida_escalamiento(session, fila, con_destinatarios=True)
    session.commit()
    return salida


@router.post(
    "/escalamientos/{escalamiento_id}/elevar",
    response_model=schemas.EscalamientoDetalleOut,
)
def elevar_escalamiento(
    escalamiento_id: uuid.UUID,
    body: schemas.AccionEscalamientoIn,
    actor: Usuario = Depends(require_permission(ESCALAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    """Sube un escalón. La respuesta trae `destinatarios`: si va vacía, el
    nivel de destino no tiene a nadie y quien eleva tiene que saberlo en vez
    de suponer que llegó (RN-REP-005)."""
    fila = exigir_escalamiento(session, escalamiento_id, tenant)
    reporte = _exigir_puerta_doble(session, fila.reporte_emitido_id, actor, tenant)
    escalamientos.elevar(
        session,
        fila,
        reporte,
        descripcion=body.descripcion,
        usuario_id=actor.id,
        ip=ip,
    )
    salida = _a_salida_escalamiento(session, fila, con_destinatarios=True)
    session.commit()
    return salida


@router.post(
    "/escalamientos/{escalamiento_id}/resolver",
    response_model=schemas.EscalamientoDetalleOut,
)
def resolver_escalamiento(
    escalamiento_id: uuid.UUID,
    body: schemas.AccionEscalamientoIn,
    actor: Usuario = Depends(require_permission(RESOLVER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
    ip: str | None = Depends(client_ip),
):
    fila = exigir_escalamiento(session, escalamiento_id, tenant)
    reporte = _exigir_puerta_doble(session, fila.reporte_emitido_id, actor, tenant)
    escalamientos.resolver(
        session,
        fila,
        reporte,
        descripcion=body.descripcion,
        usuario_id=actor.id,
        ip=ip,
    )
    salida = _a_salida_escalamiento(session, fila)
    session.commit()
    return salida


@router.get("/emitidos/{reporte_id}", response_model=schemas.ReporteEmitidoDetalleOut)
def detalle_emitido(
    reporte_id: uuid.UUID,
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db_reportes),
):
    """Doble puerta (RN-REP-002), en `_exigir_puerta_doble`: alcance —ser
    destinatario o tener `reports.leer_todo`— y contenido —el permiso del
    módulo dueño de la emisión—. Estar en la lista de distribución no otorga
    acceso al dato, mismo criterio que el addendum de ADR-024 para los
    tableros compartidos."""
    reporte = _exigir_puerta_doble(session, reporte_id, usuario, tenant)
    entregas = ReporteEmitidoRepo(session).entregas(reporte_id)
    nombres = _nombres_de(
        session, [e.usuario_id for e in entregas] + [reporte.actor_id]
    )

    salida = schemas.ReporteEmitidoDetalleOut.model_validate(
        reporte, from_attributes=True
    )
    salida.actor = _nombre_actor(reporte.actor_id, nombres)
    salida.referencia_url = destinos.url(
        reporte.referencia_tipo, reporte.referencia_id
    )
    salida.entregas = [
        schemas.EntregaReporteOut(
            usuario_id=e.usuario_id,
            usuario=nombres.get(e.usuario_id, "(borrado)"),
            motivo=e.motivo,
            canal=e.canal,
        )
        for e in entregas
    ]
    return salida
