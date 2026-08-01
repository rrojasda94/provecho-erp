"""Routers FastAPI del módulo inventory: catálogo, stock y ajustes.

Reusa las dependencias de auth/RBAC del módulo users (mecanismo transversal).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.inventory.api import schemas
from src.modules.inventory.application import ajustes, catalogo
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.scope import (
    exigir_ajuste,
    exigir_almacen,
    exigir_articulo,
    exigir_lote,
)
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/inventory", tags=["inventory"])

LEER = "inventory.leer"
CATALOGO = "inventory.gestionar_catalogo"
MOVIMIENTO = "inventory.registrar_movimiento"
SOLICITAR = "inventory.solicitar_ajuste"
APROBAR = "inventory.aprobar_ajuste"


# --- Categorías -------------------------------------------------------------
@router.post("/categorias", response_model=schemas.CategoriaOut, status_code=201)
def crear_categoria(
    body: schemas.CategoriaCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    cat = catalogo.crear_categoria(
        session,
        empresa_id=tenant.empresa(body.empresa_id),
        nombre=body.nombre,
        asiento_contable_config=body.asiento_contable_config,
    )
    session.commit()
    return cat


@router.get("/categorias", response_model=list[schemas.CategoriaOut])
def listar_categorias(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return catalogo.listar_categorias(session, tenant.filtro_empresa(empresa_id))


# --- Artículos --------------------------------------------------------------
@router.post("/articulos", response_model=schemas.ArticuloOut, status_code=201)
def crear_articulo(
    body: schemas.ArticuloCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    art = catalogo.crear_articulo(
        session,
        empresa_id=tenant.empresa(body.empresa_id),
        id_interno=body.id_interno,
        nombre=body.nombre,
        unidad_medida_id=body.unidad_medida_id,
        tipo=body.tipo,
        categoria_id=body.categoria_id,
        costo_promedio=body.costo_promedio,
        controla_lote=body.controla_lote,
    )
    session.commit()
    return art


@router.get("/articulos", response_model=list[schemas.ArticuloOut])
def listar_articulos(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return catalogo.listar_articulos(session, tenant.filtro_empresa(empresa_id))


@router.patch("/articulos/{articulo_id}", response_model=schemas.ArticuloOut)
def editar_articulo(
    articulo_id: uuid.UUID,
    body: schemas.ArticuloUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_articulo(session, articulo_id, tenant)
    art = catalogo.editar_articulo(session, articulo_id, **body.model_dump())
    session.commit()
    return art


# --- SKU --------------------------------------------------------------------
@router.post("/skus", response_model=schemas.SkuOut, status_code=201)
def crear_sku(
    body: schemas.SkuCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_articulo(session, body.articulo_id, tenant)
    sku = catalogo.crear_sku(
        session,
        articulo_id=body.articulo_id,
        codigo=body.codigo,
        codigo_barras=body.codigo_barras,
    )
    session.commit()
    return sku


# --- Stock / movimientos ----------------------------------------------------
@router.get("/stock", response_model=list[schemas.StockOut])
def consultar_stock(
    almacen_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return stock_uc.consultar_stock(session, almacen_id, tenant.filtro_empresa())


@router.post("/movimientos", response_model=list[schemas.MovimientoOut], status_code=201)
def registrar_movimiento(
    body: schemas.MovimientoCreate,
    actor: Usuario = Depends(require_permission(MOVIMIENTO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Devuelve una lista porque una salida FEFO puede repartirse entre
    varios lotes, y cada lote es un movimiento propio (ADR-015)."""
    exigir_almacen(session, body.almacen_id, tenant)
    if body.lote_id is not None:
        exigir_lote(session, body.lote_id, tenant)
    if body.cantidad < 0:
        movs = stock_uc.registrar_salida(
            session,
            almacen_id=body.almacen_id,
            sku_id=body.sku_id,
            cantidad=-body.cantidad,
            tipo=body.tipo,
            usuario_id=actor.id,
            referencia=body.referencia,
            lote_id=body.lote_id,
        )
    else:
        mov, _ = stock_uc.registrar_movimiento(
            session,
            almacen_id=body.almacen_id,
            sku_id=body.sku_id,
            cantidad=body.cantidad,
            tipo=body.tipo,
            usuario_id=actor.id,
            referencia=body.referencia,
            lote_id=body.lote_id,
            id=body.id,
        )
        movs = [mov]
    session.commit()
    return movs


# --- Lotes / FEFO -----------------------------------------------------------
@router.post("/lotes", response_model=schemas.LoteOut, status_code=201)
def crear_lote(
    body: schemas.LoteCreate,
    _: Usuario = Depends(require_permission(MOVIMIENTO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_articulo(session, body.articulo_id, tenant)
    lote = lotes_uc.crear_lote(session, **body.model_dump())
    session.commit()
    return lote


@router.get("/lotes", response_model=list[schemas.StockLoteOut])
def listar_lotes(
    almacen_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    por_vencer_dias: int | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Saldo por lote en orden de vencimiento. `por_vencer_dias` acota a los
    que vencen dentro de esa ventana (incluye los ya vencidos)."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return lotes_uc.listar(
        session,
        almacen_id=almacen_id,
        sku_id=sku_id,
        empresa_id=tenant.filtro_empresa(),
        por_vencer_dias=por_vencer_dias,
    )


@router.post("/lotes/bloquear-vencidos", response_model=list[schemas.StockLoteOut])
def bloquear_vencidos(
    almacen_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(MOVIMIENTO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Barrido de vencidos: bloquea y publica `inventory.lote_vencido_detectado`.
    El picking ya lo hace al tocar cada lote; esto lo adelanta a demanda."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    bloqueados = lotes_uc.bloquear_vencidos(
        session, almacen_id, tenant.filtro_empresa()
    )
    ids = [b.lote_id for b in bloqueados]
    session.commit()
    return [
        fila
        for fila in lotes_uc.listar(
            session, almacen_id=almacen_id, empresa_id=tenant.filtro_empresa()
        )
        if fila["lote_id"] in ids
    ]


# --- Ajustes (segregación solicitar/aprobar) --------------------------------
@router.post("/ajustes", response_model=schemas.AjusteOut, status_code=201)
def solicitar_ajuste(
    body: schemas.AjusteCreate,
    actor: Usuario = Depends(require_permission(SOLICITAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_almacen(session, body.almacen_id, tenant)
    aj = ajustes.solicitar_ajuste(
        session,
        almacen_id=body.almacen_id,
        sku_id=body.sku_id,
        cantidad=body.cantidad,
        motivo=body.motivo,
        solicitado_por=actor.id,
        dentro_margen=body.dentro_margen,
    )
    session.commit()
    return aj


@router.post("/ajustes/{ajuste_id}/aprobar", response_model=schemas.AjusteOut)
def aprobar_ajuste(
    ajuste_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(APROBAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_ajuste(session, ajuste_id, tenant)
    aj = ajustes.aprobar_ajuste(session, ajuste_id, actor.id)
    session.commit()
    return aj


@router.post("/ajustes/{ajuste_id}/rechazar", response_model=schemas.AjusteOut)
def rechazar_ajuste(
    ajuste_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(APROBAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_ajuste(session, ajuste_id, tenant)
    aj = ajustes.rechazar_ajuste(session, ajuste_id, actor.id)
    session.commit()
    return aj
