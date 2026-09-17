"""Routers FastAPI del módulo supervision: categorías, plantillas, tareas
del día e informe diario."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.tenant import Tenant
from src.modules.supervision.api import schemas
from src.modules.supervision.application import categorias, generacion, informes, plantillas, tareas
from src.modules.supervision.application.errors import ReglaNegocio
from src.modules.supervision.application.fotos import MIME_PERMITIDOS
from src.modules.supervision.application.scope import (
    exigir_categoria,
    exigir_informe,
    exigir_instancia,
    exigir_plantilla,
    exigir_sucursal,
)
from src.modules.supervision.infrastructure.models import TareaInstancia
from src.modules.users.api.deps import (
    get_current_user,
    get_db,
    get_tenant,
    require_permission,
    tiene_permiso,
)
from src.modules.users.infrastructure.models import Usuario
from src.shared import fechas
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/supervision", tags=["supervision"])

GESTIONAR = "supervision.gestionar"
LEER = "supervision.leer"
EJECUTAR = "supervision.ejecutar"


def _tarea_out(instancia: TareaInstancia) -> schemas.TareaInstanciaOut:
    salida = schemas.TareaInstanciaOut.model_validate(instancia)
    salida.tiene_foto = instancia.foto is not None
    return salida


def _puede_ver_tarea(session: Session, actor: Usuario, instancia: TareaInstancia) -> bool:
    """`supervision.leer` ve cualquiera de su tenant; sin ese permiso, solo
    el trabajador asignado ve su propia tarea."""
    return tiene_permiso(session, actor, LEER) or instancia.asignado_a == actor.id


# --- Categorías --------------------------------------------------------------
@router.post("/categorias", response_model=schemas.CategoriaOut, status_code=201)
def crear_categoria(
    body: schemas.CategoriaCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    categoria = categorias.crear_categoria(
        session, empresa_id=tenant.empresa(body.empresa_id), nombre=body.nombre
    )
    session.commit()
    return categoria


@router.get("/categorias", response_model=list[schemas.CategoriaOut])
def listar_categorias(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return list(
        session.scalars(categorias.q_categorias(session, tenant.filtro_empresa(empresa_id)))
    )


@router.patch("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def editar_categoria(
    categoria_id: uuid.UUID,
    body: schemas.CategoriaUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_categoria(session, categoria_id, tenant)
    categoria = categorias.editar_categoria(session, categoria_id, **body.model_dump())
    session.commit()
    return categoria


# --- Plantillas ----------------------------------------------------------------
@router.post("/plantillas", response_model=schemas.PlantillaOut, status_code=201)
def crear_plantilla(
    body: schemas.PlantillaCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_categoria(session, body.categoria_id, tenant)
    if body.sucursal_id is not None:
        exigir_sucursal(session, body.sucursal_id, tenant)
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    try:
        plantilla = plantillas.crear_plantilla(session, **campos)
    except ReglaNegocio as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session.commit()
    return plantilla


@router.get("/plantillas", response_model=Pagina[schemas.PlantillaOut])
def listar_plantillas(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(session, plantillas.q_plantillas(session, tenant.filtro_empresa(empresa_id)), p)


@router.patch("/plantillas/{plantilla_id}", response_model=schemas.PlantillaOut)
def editar_plantilla(
    plantilla_id: uuid.UUID,
    body: schemas.PlantillaUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_plantilla(session, plantilla_id, tenant)
    plantilla = plantillas.editar_plantilla(session, plantilla_id, **body.model_dump())
    session.commit()
    return plantilla


@router.delete("/plantillas/{plantilla_id}", response_model=schemas.PlantillaOut)
def desactivar_plantilla(
    plantilla_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_plantilla(session, plantilla_id, tenant)
    plantilla = plantillas.desactivar_plantilla(session, plantilla_id)
    session.commit()
    return plantilla


# --- Tareas del día ------------------------------------------------------------
@router.post("/tareas", response_model=schemas.TareaInstanciaOut, status_code=201)
def crear_tarea_manual(
    body: schemas.TareaManualCreate,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_sucursal(session, body.sucursal_id, tenant)
    exigir_categoria(session, body.categoria_id, tenant)
    instancia = generacion.crear_tarea_manual(session, **body.model_dump())
    session.commit()
    return _tarea_out(instancia)


@router.post("/tareas/generar")
def generar_tareas(
    fecha: date | None = None,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    generadas = generacion.generar_instancias(
        session, fecha or fechas.hoy(), tenant.filtro_empresa(None)
    )
    session.commit()
    return {"generadas": generadas}


@router.get("/tareas", response_model=list[schemas.TareaInstanciaOut])
def listar_tareas(
    sucursal_id: uuid.UUID,
    fecha: date | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_sucursal(session, sucursal_id, tenant)
    instancias = session.scalars(
        tareas.q_tareas_de_sucursal(session, sucursal_id, fecha or fechas.hoy())
    )
    return [_tarea_out(i) for i in instancias]


@router.get("/tareas/mias", response_model=list[schemas.TareaInstanciaOut])
def listar_mis_tareas(
    fecha: date | None = None,
    actor: Usuario = Depends(require_permission(EJECUTAR)),
    session: Session = Depends(get_db),
):
    instancias = session.scalars(tareas.q_mis_tareas(session, actor.id, fecha or fechas.hoy()))
    return [_tarea_out(i) for i in instancias]


@router.get("/tareas/{instancia_id}", response_model=schemas.TareaInstanciaOut)
def ver_tarea(
    instancia_id: uuid.UUID,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    instancia = exigir_instancia(session, instancia_id, tenant)
    if not _puede_ver_tarea(session, actor, instancia):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado")
    return _tarea_out(instancia)


@router.patch("/tareas/{instancia_id}/asignar", response_model=schemas.TareaInstanciaOut)
def asignar_tarea(
    instancia_id: uuid.UUID,
    body: schemas.AsignarBody,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_instancia(session, instancia_id, tenant)
    instancia = generacion.asignar(session, instancia_id, usuario_id=body.usuario_id)
    session.commit()
    return _tarea_out(instancia)


@router.patch(
    "/tareas/{instancia_id}/checklist/{indice}", response_model=schemas.TareaInstanciaOut
)
def marcar_item(
    instancia_id: uuid.UUID,
    indice: int,
    body: schemas.MarcarItemBody,
    actor: Usuario = Depends(require_permission(EJECUTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_instancia(session, instancia_id, tenant)
    try:
        instancia = tareas.marcar_item(
            session, instancia_id, indice, hecho=body.hecho, actor_id=actor.id
        )
    except ReglaNegocio as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    session.commit()
    return _tarea_out(instancia)


@router.post("/tareas/{instancia_id}/foto", response_model=schemas.TareaInstanciaOut)
async def subir_foto(
    instancia_id: uuid.UUID,
    archivo: UploadFile,
    actor: Usuario = Depends(require_permission(EJECUTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_instancia(session, instancia_id, tenant)
    if not archivo.content_type or not archivo.content_type.startswith(MIME_PERMITIDOS):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "la evidencia debe ser una imagen"
        )
    contenido = await archivo.read()
    try:
        instancia = tareas.adjuntar_foto(session, instancia_id, contenido, actor_id=actor.id)
    except ReglaNegocio as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session.commit()
    return _tarea_out(instancia)


@router.get("/tareas/{instancia_id}/foto")
def ver_foto(
    instancia_id: uuid.UUID,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    instancia = exigir_instancia(session, instancia_id, tenant)
    if not _puede_ver_tarea(session, actor, instancia):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado")
    if instancia.foto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "esta tarea no tiene foto")
    return Response(content=instancia.foto, media_type="image/jpeg")


@router.post("/tareas/{instancia_id}/completar", response_model=schemas.TareaInstanciaOut)
def completar_tarea(
    instancia_id: uuid.UUID,
    body: schemas.CompletarBody,
    actor: Usuario = Depends(require_permission(EJECUTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_instancia(session, instancia_id, tenant)
    try:
        instancia = tareas.completar(
            session,
            instancia_id,
            actor_id=actor.id,
            ahora=fechas.ahora(),
            tolerancia_minutos=settings.supervision_foto_tolerancia_minutos,
            observacion=body.observacion,
        )
    except ReglaNegocio as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session.commit()
    return _tarea_out(instancia)


# --- Informe diario --------------------------------------------------------------
@router.post("/informes/generar", response_model=schemas.InformeDiarioOut)
def generar_informe(
    sucursal_id: uuid.UUID,
    fecha: date | None = None,
    _: Usuario = Depends(require_permission(GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_sucursal(session, sucursal_id, tenant)
    informe = informes.generar_informe(
        session, sucursal_id=sucursal_id, fecha=fecha or fechas.hoy(), ahora=fechas.ahora()
    )
    session.commit()
    return informe


@router.get("/informes", response_model=Pagina[schemas.InformeDiarioOut])
def listar_informes(
    sucursal_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(session, informes.q_informes(session, sucursal_id), p)


@router.get("/informes/{informe_id}", response_model=schemas.InformeDiarioOut)
def ver_informe(
    informe_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_informe(session, informe_id, tenant)
