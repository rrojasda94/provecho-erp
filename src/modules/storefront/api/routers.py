"""Gestión del sitio de marca: CMS de contenido y fotos de catálogo
(JWT + `storefront.leer`/`storefront.editar`, ADR-103)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.modules.storefront.api import schemas
from src.modules.storefront.application import contenido, fotos
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/storefront", tags=["storefront"])

LEER = "storefront.leer"
EDITAR = "storefront.editar"


# --- Contenido (CMS mínimo) --------------------------------------------------
@router.get("/contenido", response_model=list[schemas.ContenidoOut])
def listar_contenido(
    marca_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    filas = contenido.listar(session, marca_id)
    return [
        {
            "clave": f.clave,
            "valor": f.valor,
            "updated_by": f.updated_by,
            "updated_at": f.updated_at,
        }
        for f in filas
    ]


@router.put("/contenido/{clave}", response_model=schemas.ContenidoOut)
def guardar_contenido(
    clave: schemas.ClaveContenido,
    marca_id: uuid.UUID,
    body: schemas.ContenidoIn,
    actor: Usuario = Depends(require_permission(EDITAR)),
    session: Session = Depends(get_db),
):
    fila = contenido.guardar(
        session, marca_id=marca_id, clave=clave, valor=body.valor, actor_id=actor.id
    )
    session.commit()
    return {
        "clave": fila.clave,
        "valor": fila.valor,
        "updated_by": fila.updated_by,
        "updated_at": fila.updated_at,
    }


# --- Fotos de catálogo --------------------------------------------------------
@router.post(
    "/fotos/{entidad}/{entidad_id}/presign-upload",
    response_model=schemas.PresignFotoOut,
)
def presignar_foto(
    entidad: schemas.EntidadFoto,
    entidad_id: uuid.UUID,
    body: schemas.PresignFotoIn,
    _: Usuario = Depends(require_permission(EDITAR)),
    session: Session = Depends(get_db),
):
    return fotos.presignar(
        session,
        entidad=entidad,
        entidad_id=entidad_id,
        nombre=body.nombre,
        mime_type=body.mime_type,
    )


@router.post(
    "/fotos/{entidad}/{entidad_id}", response_model=schemas.FotoOut, status_code=201
)
def registrar_foto(
    entidad: schemas.EntidadFoto,
    entidad_id: uuid.UUID,
    body: schemas.FotoRegistrarIn,
    actor: Usuario = Depends(require_permission(EDITAR)),
    session: Session = Depends(get_db),
):
    archivo = fotos.registrar(
        session,
        entidad=entidad,
        entidad_id=entidad_id,
        nombre=body.nombre,
        mime_type=body.mime_type,
        tamano_bytes=body.tamano_bytes,
        url_storage=body.url_storage,
        subido_por=actor.id,
    )
    session.commit()
    return archivo


@router.get("/fotos/{entidad}/{entidad_id}", response_model=list[schemas.FotoOut])
def listar_fotos(
    entidad: schemas.EntidadFoto,
    entidad_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return fotos.listar(session, entidad=entidad, entidad_id=entidad_id)


@router.delete("/fotos/{archivo_id}", status_code=204)
def borrar_foto(
    archivo_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(EDITAR)),
    session: Session = Depends(get_db),
):
    fotos.borrar(session, archivo_id=archivo_id, actor_id=actor.id)
    session.commit()
