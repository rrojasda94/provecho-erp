"""Gestión del sitio de marca: CMS de contenido y fotos de catálogo
(JWT + `storefront.leer`/`storefront.editar`, ADR-103)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.modules.storefront.api import schemas
from src.modules.storefront.application import atencion, contenido, fotos
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Usuario
from src.shared.integrations.email import smtp

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


# --- Atención al cliente: cuentas del sitio ------------------------------------
@router.get("/clientes/correo", response_model=schemas.CorreoSalienteOut)
def estado_del_correo(
    _: Usuario = Depends(require_permission(LEER)),
):
    """Si el servidor puede mandar correos.

    Sin `SMTP_HOST` el enlace de "olvidé mi contraseña" se genera y no sale a
    ningún lado: el sitio responde lo mismo de siempre (no puede delatar qué
    correos tienen cuenta, RN-WEB-018) y desde afuera es indistinguible de un
    envío real. Quien atiende tiene que poder saberlo para ofrecer el
    restablecimiento asistido en vez de mandar a esperar un correo que no
    existe.
    """
    return {"configurado": smtp.configurado()}


@router.get("/clientes", response_model=list[schemas.ClienteWebOut])
def listar_clientes_web(
    q: str | None = Query(default=None, max_length=100),
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return [
        {
            **{c: getattr(cuenta, c) for c in schemas.ClienteWebOut.model_fields
               if hasattr(cuenta, c)},
            "tiene_password": cuenta.password_hash is not None,
            "tiene_google": cuenta.google_sub is not None,
        }
        for cuenta in atencion.listar(session, q=q)
    ]


@router.post(
    "/clientes/{cuenta_id}/restablecer-clave", response_model=schemas.ClaveTemporalOut
)
def restablecer_clave_de_cliente(
    cuenta_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(EDITAR)),
    session: Session = Depends(get_db),
):
    """Para quien no tiene un correo al que llegue el enlace. Devuelve la clave
    temporal **una sola vez**; la cuenta queda obligada a cambiarla."""
    clave = atencion.restablecer_por_atencion(
        session, cuenta_id=cuenta_id, actor_id=actor.id
    )
    session.commit()
    return {"clave_temporal": clave}


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


@router.get("/fotos", response_model=dict[uuid.UUID, list[schemas.FotoOut]])
def listar_fotos_varias(
    entidad: schemas.EntidadFoto,
    ids: list[uuid.UUID] = Query(max_length=500),
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Las fotos de muchas entidades en una sola llamada
    (`?entidad=producto&ids=a&ids=b`) —
    las pantallas `/web` del ERP pedían una por producto y agotaban el pool
    de conexiones."""
    return fotos.listar_varias(session, entidad=entidad, entidad_ids=ids)


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
