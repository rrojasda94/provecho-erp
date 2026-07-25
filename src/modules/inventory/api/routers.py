"""Routers FastAPI del módulo inventory: catálogo, stock y ajustes.

Reusa las dependencias de auth/RBAC del módulo users (mecanismo transversal).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.modules.inventory.api import schemas
from src.modules.inventory.application import ajustes, catalogo
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import (
    Conflicto,
    InventoryError,
    NoEncontrado,
    ReglaNegocio,
    StockInsuficiente,
)
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/inventory", tags=["inventory"])

LEER = "inventory.leer"
CATALOGO = "inventory.gestionar_catalogo"
MOVIMIENTO = "inventory.registrar_movimiento"
SOLICITAR = "inventory.solicitar_ajuste"
APROBAR = "inventory.aprobar_ajuste"

_HTTP_STATUS: dict[type[InventoryError], int] = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ReglaNegocio: status.HTTP_409_CONFLICT,
    StockInsuficiente: status.HTTP_409_CONFLICT,
}


def _http(err: InventoryError) -> HTTPException:
    return HTTPException(_HTTP_STATUS.get(type(err), 400), str(err))


# --- Categorías -------------------------------------------------------------
@router.post("/categorias", response_model=schemas.CategoriaOut, status_code=201)
def crear_categoria(
    body: schemas.CategoriaCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    try:
        cat = catalogo.crear_categoria(
            session,
            empresa_id=body.empresa_id,
            nombre=body.nombre,
            asiento_contable_config=body.asiento_contable_config,
        )
    except Conflicto as e:
        raise _http(e) from e
    session.commit()
    return cat


@router.get("/categorias", response_model=list[schemas.CategoriaOut])
def listar_categorias(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return catalogo.listar_categorias(session, empresa_id)


# --- Artículos --------------------------------------------------------------
@router.post("/articulos", response_model=schemas.ArticuloOut, status_code=201)
def crear_articulo(
    body: schemas.ArticuloCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    try:
        art = catalogo.crear_articulo(
            session,
            empresa_id=body.empresa_id,
            id_interno=body.id_interno,
            nombre=body.nombre,
            unidad_medida_id=body.unidad_medida_id,
            tipo=body.tipo,
            categoria_id=body.categoria_id,
            costo_promedio=body.costo_promedio,
        )
    except (Conflicto, NoEncontrado) as e:
        raise _http(e) from e
    session.commit()
    return art


@router.get("/articulos", response_model=list[schemas.ArticuloOut])
def listar_articulos(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return catalogo.listar_articulos(session, empresa_id)


@router.patch("/articulos/{articulo_id}", response_model=schemas.ArticuloOut)
def editar_articulo(
    articulo_id: uuid.UUID,
    body: schemas.ArticuloUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    try:
        art = catalogo.editar_articulo(session, articulo_id, **body.model_dump())
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return art


# --- SKU --------------------------------------------------------------------
@router.post("/skus", response_model=schemas.SkuOut, status_code=201)
def crear_sku(
    body: schemas.SkuCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    try:
        sku = catalogo.crear_sku(
            session,
            articulo_id=body.articulo_id,
            codigo=body.codigo,
            codigo_barras=body.codigo_barras,
        )
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return sku


# --- Stock / movimientos ----------------------------------------------------
@router.get("/stock", response_model=list[schemas.StockOut])
def consultar_stock(
    almacen_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return stock_uc.consultar_stock(session, almacen_id)


@router.post("/movimientos", response_model=schemas.MovimientoOut, status_code=201)
def registrar_movimiento(
    body: schemas.MovimientoCreate,
    actor: Usuario = Depends(require_permission(MOVIMIENTO)),
    session: Session = Depends(get_db),
):
    try:
        mov, _ = stock_uc.registrar_movimiento(
            session,
            almacen_id=body.almacen_id,
            sku_id=body.sku_id,
            cantidad=body.cantidad,
            tipo=body.tipo,
            usuario_id=actor.id,
            referencia=body.referencia,
        )
    except (ReglaNegocio, StockInsuficiente) as e:
        raise _http(e) from e
    session.commit()
    return mov


# --- Ajustes (segregación solicitar/aprobar) --------------------------------
@router.post("/ajustes", response_model=schemas.AjusteOut, status_code=201)
def solicitar_ajuste(
    body: schemas.AjusteCreate,
    actor: Usuario = Depends(require_permission(SOLICITAR)),
    session: Session = Depends(get_db),
):
    try:
        aj = ajustes.solicitar_ajuste(
            session,
            almacen_id=body.almacen_id,
            sku_id=body.sku_id,
            cantidad=body.cantidad,
            motivo=body.motivo,
            solicitado_por=actor.id,
            dentro_margen=body.dentro_margen,
        )
    except ReglaNegocio as e:
        raise _http(e) from e
    session.commit()
    return aj


@router.post("/ajustes/{ajuste_id}/aprobar", response_model=schemas.AjusteOut)
def aprobar_ajuste(
    ajuste_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(APROBAR)),
    session: Session = Depends(get_db),
):
    try:
        aj = ajustes.aprobar_ajuste(session, ajuste_id, actor.id)
    except (NoEncontrado, ReglaNegocio, StockInsuficiente) as e:
        raise _http(e) from e
    session.commit()
    return aj


@router.post("/ajustes/{ajuste_id}/rechazar", response_model=schemas.AjusteOut)
def rechazar_ajuste(
    ajuste_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(APROBAR)),
    session: Session = Depends(get_db),
):
    try:
        aj = ajustes.rechazar_ajuste(session, ajuste_id, actor.id)
    except (NoEncontrado, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return aj
