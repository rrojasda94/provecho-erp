"""Routers FastAPI del módulo delivery: repartidores, rutas, entregas y el
GPS de una ruta en curso (ADR-098). El seguimiento público del cliente
vive aparte, en `api/publico_routers.py` — es la única superficie de
`delivery` sin JWT.
"""

import base64
import binascii
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.core.rate_limit import consumir
from src.core.tenant import Tenant
from src.modules.delivery.api import schemas
from src.modules.delivery.application import entregas, mi_reparto, posiciones, repartidores
from src.modules.delivery.application import rutas as rutas_uc
from src.modules.delivery.application import tablero as tablero_uc
from src.modules.delivery.application.scope import (
    exigir_entrega,
    exigir_entrega_de_ruta_propia,
    exigir_repartidor,
    exigir_ruta,
    exigir_ruta_propia,
)
from src.modules.delivery.infrastructure.models import Entrega, RutaReparto
from src.modules.delivery.infrastructure.repositories import EntregaRepo, RepartidorRepo
from src.modules.users.api.deps import (
    check_permission,
    get_current_user,
    get_db,
    get_tenant,
    require_permission,
)
from src.modules.users.application.queries_publicas import tiene_permiso
from src.modules.users.infrastructure.models import Usuario
from src.shared import fechas
from src.shared.integrations import whatsapp
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/delivery", tags=["delivery"])

LEER = "delivery.leer"
DESPACHAR = "delivery.despachar"
GESTIONAR_REPARTIDORES = "delivery.gestionar_repartidores"
REPARTIR = "delivery.repartir"

# Tope tras decodificar el base64 — mismo número y mismo motivo que
# `rrhh.api.routers.FOTO_MAX_BYTES`.
FOTO_MAX_BYTES = 130_000


def _decodificar_foto(foto: str | None) -> bytes | None:
    if not foto:
        return None
    try:
        binario = base64.b64decode(foto, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(422, "foto inválida: no es base64 válido") from e
    if len(binario) > FOTO_MAX_BYTES:
        raise HTTPException(422, f"la foto supera el máximo de {FOTO_MAX_BYTES // 1024} KB")
    return binario


def _sucursales_del_alcance(
    tenant: Tenant, sucursal_id: uuid.UUID | None
) -> list[uuid.UUID] | None:
    """Mismo criterio que `GET /sales/ventas`: con `sucursal_id` explícito
    se acota a esa (validando alcance); sin filtro, todas las del usuario
    — o ninguna acotación para el superusuario, que ya las ve todas."""
    if sucursal_id is not None:
        tenant.exigir_sucursal(sucursal_id)
        return [sucursal_id]
    if tenant.superusuario:
        return None
    return list(tenant.sucursal_ids)


def _autorizar_sobre_ruta(session: Session, actor: Usuario, ruta: RutaReparto) -> None:
    """`delivery.despachar` alcanza para cualquier ruta de la sucursal;
    `delivery.repartir` solo para la propia (ver `exigir_ruta_propia`)."""
    check_permission(session, actor, DESPACHAR, REPARTIR)
    if not tiene_permiso(session, actor.id, DESPACHAR):
        exigir_ruta_propia(session, ruta, actor.id)


def _autorizar_sobre_entrega(session: Session, actor: Usuario, entrega: Entrega) -> None:
    check_permission(session, actor, DESPACHAR, REPARTIR)
    if not tiene_permiso(session, actor.id, DESPACHAR):
        exigir_entrega_de_ruta_propia(session, entrega, actor.id)


# --- Repartidores -------------------------------------------------------------
@router.get(
    "/repartidores/candidatos",
    response_model=list[schemas.RepartidorCandidatoOut],
)
def listar_candidatos(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(GESTIONAR_REPARTIDORES)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return repartidores.candidatos(session, tenant.empresa(empresa_id))


@router.post("/repartidores", response_model=schemas.RepartidorOut, status_code=201)
def crear_repartidor(
    body: schemas.RepartidorCreate,
    _: Usuario = Depends(require_permission(GESTIONAR_REPARTIDORES)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
    repartidor = repartidores.crear(
        session,
        empresa_id=tenant.empresa(),
        trabajador_id=body.trabajador_id,
        sucursal_id=body.sucursal_id,
        vehiculo_tipo=body.vehiculo_tipo,
        placa=body.placa,
        telefono=body.telefono,
    )
    session.commit()
    return repartidores.con_nombre(session, repartidor)


@router.get("/repartidores", response_model=list[schemas.RepartidorOut])
def listar_repartidores(
    sucursal_id: uuid.UUID | None = None,
    activo: bool | None = None,
    usuario: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    check_permission(session, usuario, LEER, DESPACHAR)
    if sucursal_id is not None:
        tenant.exigir_sucursal(sucursal_id)
        encontrados = RepartidorRepo(session).list(sucursal_id, activo=activo)
    else:
        sucursales = None if tenant.superusuario else tenant.sucursal_ids
        repo = RepartidorRepo(session)
        encontrados = (
            repo.list(activo=activo)
            if sucursales is None
            else [r for r in repo.list(activo=activo) if r.sucursal_id in sucursales]
        )
    return [repartidores.con_nombre(session, r) for r in encontrados]


@router.patch("/repartidores/{repartidor_id}", response_model=schemas.RepartidorOut)
def editar_repartidor(
    repartidor_id: uuid.UUID,
    body: schemas.RepartidorUpdate,
    _: Usuario = Depends(require_permission(GESTIONAR_REPARTIDORES)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_repartidor(session, repartidor_id, tenant)
    if body.sucursal_id is not None:
        tenant.exigir_sucursal(body.sucursal_id)
    repartidor = repartidores.editar(session, repartidor_id, **body.model_dump())
    session.commit()
    return repartidores.con_nombre(session, repartidor)


# --- Tablero de despacho -------------------------------------------------------
@router.get("/tablero", response_model=schemas.TableroOut)
def ver_tablero(
    sucursal_id: uuid.UUID,
    fecha: date | None = None,
    _: Usuario = Depends(require_permission(DESPACHAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(sucursal_id)
    return {
        "sin_asignar": tablero_uc.sin_asignar(session, [sucursal_id], fecha=fecha),
        "rutas": tablero_uc.rutas_vivas(session, [sucursal_id]),
        "whatsapp_habilitado": whatsapp.habilitado(),
    }


# --- Rutas ----------------------------------------------------------------------
@router.post("/rutas", response_model=schemas.RutaOut, status_code=201)
def crear_ruta(
    body: schemas.RutaCreate,
    actor: Usuario = Depends(require_permission(DESPACHAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
    exigir_repartidor(session, body.repartidor_id, tenant)
    ruta = rutas_uc.crear(
        session,
        empresa_id=tenant.empresa(),
        sucursal_id=body.sucursal_id,
        repartidor_id=body.repartidor_id,
        venta_ids=body.venta_ids,
        optimizar=body.optimizar,
        creada_por=actor.id,
    )
    session.commit()
    return ruta


@router.get("/rutas", response_model=Pagina[schemas.RutaOut])
def listar_rutas(
    sucursal_id: uuid.UUID | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    sucursales = _sucursales_del_alcance(tenant, sucursal_id)
    return paginar(session, rutas_uc.q_list(session, sucursales, estado=estado), p)


@router.get("/rutas/{ruta_id}", response_model=schemas.RutaOut)
def ver_ruta(
    ruta_id: uuid.UUID,
    usuario: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    ruta = exigir_ruta(session, ruta_id, tenant)
    check_permission(session, usuario, LEER, REPARTIR)
    if not tiene_permiso(session, usuario.id, LEER):
        exigir_ruta_propia(session, ruta, usuario.id)
    return ruta


@router.put("/rutas/{ruta_id}/paradas", response_model=schemas.RutaOut)
def editar_paradas(
    ruta_id: uuid.UUID,
    body: schemas.RutaParadasUpdate,
    actor: Usuario = Depends(require_permission(DESPACHAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_ruta(session, ruta_id, tenant)
    ruta = rutas_uc.editar_paradas(
        session,
        ruta_id,
        venta_ids=body.venta_ids,
        optimizar=body.optimizar,
        empresa_id=tenant.empresa(),
        actor_id=actor.id,
    )
    session.commit()
    return ruta


@router.post("/rutas/{ruta_id}/iniciar", response_model=schemas.RutaOut)
def iniciar_ruta(
    ruta_id: uuid.UUID,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    ruta = exigir_ruta(session, ruta_id, tenant)
    _autorizar_sobre_ruta(session, actor, ruta)
    ruta = rutas_uc.iniciar(session, ruta_id, actor_id=actor.id)
    session.commit()
    return ruta


@router.post("/rutas/{ruta_id}/finalizar", response_model=schemas.RutaOut)
def finalizar_ruta(
    ruta_id: uuid.UUID,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    ruta = exigir_ruta(session, ruta_id, tenant)
    _autorizar_sobre_ruta(session, actor, ruta)
    ruta = rutas_uc.finalizar(session, ruta_id, actor_id=actor.id)
    session.commit()
    return ruta


@router.post("/rutas/{ruta_id}/cancelar", response_model=schemas.RutaOut)
def cancelar_ruta(
    ruta_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(DESPACHAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_ruta(session, ruta_id, tenant)
    ruta = rutas_uc.cancelar(session, ruta_id, actor_id=actor.id)
    session.commit()
    return ruta


@router.post("/rutas/{ruta_id}/posiciones", status_code=204)
def registrar_posicion(
    ruta_id: uuid.UUID,
    body: schemas.PosicionIn,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    ruta = exigir_ruta(session, ruta_id, tenant)
    _autorizar_sobre_ruta(session, actor, ruta)
    # Un ping cada pocos segundos por celular: el límite es por si un bug
    # del cliente manda de más, no una cuota que un repartidor normal toque.
    consumir("posicion_gps", str(actor.id), 30, 60)
    posiciones.registrar_ping(
        session,
        ruta_id,
        lat=body.lat,
        lng=body.lng,
        precision_m=body.precision_m,
        registrado_at=body.registrado_at,
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/mi/rutas", response_model=list[schemas.RutaConParadasOut])
def mis_rutas(
    actor: Usuario = Depends(require_permission(REPARTIR)),
    session: Session = Depends(get_db),
):
    repartidor = RepartidorRepo(session).get_por_usuario(actor.id)
    if repartidor is None:
        return []
    return mi_reparto.rutas_vivas(session, repartidor.id)


# --- Entregas -------------------------------------------------------------------
@router.post("/entregas/{entrega_id}/entregar", response_model=schemas.EntregaRepartoOut)
def entregar(
    entrega_id: uuid.UUID,
    body: schemas.EntregarIn,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    entrega = exigir_entrega(session, entrega_id, tenant)
    _autorizar_sobre_entrega(session, actor, entrega)
    entrega = entregas.entregar(
        session,
        entrega_id,
        actor_id=actor.id,
        lat=body.lat,
        lng=body.lng,
        foto=_decodificar_foto(body.foto),
        observacion=body.observacion,
    )
    session.commit()
    return entrega


@router.post("/entregas/{entrega_id}/fallar", response_model=schemas.EntregaRepartoOut)
def fallar(
    entrega_id: uuid.UUID,
    body: schemas.FallarIn,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    entrega = exigir_entrega(session, entrega_id, tenant)
    _autorizar_sobre_entrega(session, actor, entrega)
    entrega = entregas.fallar(
        session,
        entrega_id,
        actor_id=actor.id,
        motivo=body.motivo,
        detalle=body.detalle,
        lat=body.lat,
        lng=body.lng,
        foto=_decodificar_foto(body.foto),
    )
    session.commit()
    return entrega


@router.post("/entregas/{entrega_id}/reintentar", response_model=schemas.EntregaRepartoOut)
def reintentar(
    entrega_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(DESPACHAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_entrega(session, entrega_id, tenant)
    entrega = entregas.reintentar(session, entrega_id, actor_id=actor.id)
    session.commit()
    return entrega


@router.post("/entregas/{entrega_id}/cerrar", response_model=schemas.EntregaRepartoOut)
def cerrar(
    entrega_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(DESPACHAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_entrega(session, entrega_id, tenant)
    entrega = entregas.cerrar(session, entrega_id, actor_id=actor.id)
    session.commit()
    return entrega


@router.get("/entregas", response_model=Pagina[schemas.EntregaRepartoOut])
def listar_entregas(
    sucursal_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = None,
    repartidor_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    sucursales = _sucursales_del_alcance(tenant, sucursal_id)
    desde_dt = fechas.inicio_dia_utc(desde) if desde else None
    hasta_dt = fechas.fin_dia_utc(hasta) if hasta else None
    pagina = paginar(
        session,
        EntregaRepo(session).q_historial(
            sucursales,
            desde=desde_dt,
            hasta=hasta_dt,
            estado=estado,
            repartidor_id=repartidor_id,
        ),
        p,
    )
    return entregas.historial_enriquecido(session, pagina)


@router.get("/entregas/{entrega_id}/evidencia")
def evidencia_de_entrega(
    entrega_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    entrega = exigir_entrega(session, entrega_id, tenant)
    if entrega.evidencia_foto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "evidencia no encontrada")
    return Response(content=entrega.evidencia_foto, media_type="image/jpeg")
