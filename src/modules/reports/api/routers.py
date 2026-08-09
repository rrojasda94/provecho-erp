"""API de `reports`: catálogo, matriz de distribución, gobierno y lectura.

**No hay `POST /emitidos`.** El reporte lo emite el evento, no un cliente —
mismo criterio que ADR-031 para `audit_log`: un endpoint de escritura le
permitiría al reportado dictar lo que dice su reporte.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.reports.api import schemas
from src.modules.reports.application import areas as areas_uc
from src.modules.reports.application import matriz as matriz_uc
from src.modules.reports.application import reglas as reglas_uc
from src.modules.reports.application.scope import (
    exigir_area,
    exigir_miembro,
    exigir_regla,
    exigir_reporte,
)
from src.modules.reports.domain import catalogo
from src.modules.reports.infrastructure.repositories import ReglaRepo, ReporteEmitidoRepo
from src.modules.users.api.deps import (
    client_ip,
    get_db,
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


def _permisos(session: Session, usuario: Usuario) -> set[str]:
    return permisos_de(session, usuario.id)


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
    session: Session = Depends(get_db),
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
    )


@router.get("/matriz", response_model=list[schemas.MatrizFilaOut])
def matriz(
    usuario: Usuario = Depends(require_permission(LEER_MATRIZ)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
):
    from src.modules.reports.infrastructure.repositories import AreaRepo

    return AreaRepo(session).list(tenant.filtro_empresa())


@router.post("/areas", response_model=schemas.AreaOut, status_code=201)
def crear_area(
    body: schemas.AreaCreate,
    actor: Usuario = Depends(require_permission(ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
):
    """Lo que me fue entregado. Sin filtro de tenant explícito: la entrega ya
    es a mi `usuario_id`, y nadie me entrega reportes de otra empresa."""
    return paginar(session, ReporteEmitidoRepo(session).q_mios(usuario.id), p)


@router.get("/emitidos", response_model=Pagina[schemas.ReporteEmitidoOut])
def listar_emitidos(
    codigo_emision: str | None = None,
    _: Usuario = Depends(require_permission(LEER_TODO)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session,
        ReporteEmitidoRepo(session).q_list(
            tenant.filtro_empresa(), codigo_emision=codigo_emision
        ),
        p,
    )


@router.get("/emitidos/{reporte_id}", response_model=schemas.ReporteEmitidoDetalleOut)
def detalle_emitido(
    reporte_id: uuid.UUID,
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Doble puerta (RN-REP-002).

    1. **Alcance**: ser destinatario, o tener `reports.leer_todo`.
    2. **Contenido**: el permiso que la emisión declara, que es el de su
       módulo dueño. Estar en la lista de distribución no otorga acceso al
       dato — mismo criterio que el addendum de ADR-024 para los tableros
       compartidos.
    """
    reporte = exigir_reporte(session, reporte_id, tenant)
    repo = ReporteEmitidoRepo(session)

    permisos = _permisos(session, usuario)
    alcanza = "*" in permisos or LEER_TODO in permisos
    if not alcanza and not repo.es_destinatario(reporte_id, usuario.id):
        # Mismo 404 que si no existiera: la respuesta no confirma la
        # existencia de un reporte ajeno.
        raise HTTPException(404, "Reporte no encontrado")
    if not _emision_visible(session, usuario, reporte.codigo_emision):
        raise HTTPException(403, "Permiso denegado")

    entregas = repo.entregas(reporte_id)
    nombres = dict(
        session.execute(
            select(Usuario.id, Usuario.username).where(
                Usuario.id.in_([e.usuario_id for e in entregas])
            )
        ).all()
    ) if entregas else {}

    salida = schemas.ReporteEmitidoDetalleOut.model_validate(
        reporte, from_attributes=True
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
