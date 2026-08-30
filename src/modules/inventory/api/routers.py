"""Routers FastAPI del módulo inventory: catálogo, stock y ajustes.

Reusa las dependencias de auth/RBAC del módulo users (mecanismo transversal).
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, UploadFile
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.inventory.api import schemas
from src.modules.inventory.application import (
    ajustes,
    catalogo,
    importacion_articulos,
    importacion_recetas,
    queries_publicas,
)
from src.modules.inventory.application import conteos as conteos_uc
from src.modules.inventory.application import devoluciones as devoluciones_uc
from src.modules.inventory.application import guias as guias_uc
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application import matriz as matriz_uc
from src.modules.inventory.application import merma as merma_uc
from src.modules.inventory.application import recetas as recetas_uc
from src.modules.inventory.application import reservas as reservas_uc
from src.modules.inventory.application import solicitudes as solicitudes_uc
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application import tasks as inventory_tasks
from src.modules.inventory.application import transferencias as transferencias_uc
from src.modules.inventory.application.scope import (
    exigir_ajuste,
    exigir_almacen,
    exigir_articulo,
    exigir_categoria,
    exigir_conteo,
    exigir_devolucion,
    exigir_lote,
    exigir_receta,
    exigir_reserva,
    exigir_sku,
    exigir_solicitud,
    exigir_transferencia,
)
from src.modules.users.api.deps import (
    get_db,
    get_tenant,
    require_permission,
    tiene_permiso,
)
from src.modules.users.infrastructure.models import Usuario
from src.shared import planilla
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/inventory", tags=["inventory"])

LEER = "inventory.leer"
CATALOGO = "inventory.gestionar_catalogo"
MOVIMIENTO = "inventory.registrar_movimiento"
SOLICITAR = "inventory.solicitar_ajuste"
APROBAR = "inventory.aprobar_ajuste"
CONTAR = "inventory.contar"
VER_ESPERADO = "inventory.ver_stock_esperado"
SOLICITAR_INSUMOS = "inventory.solicitar_insumos"
APROBAR_SOLICITUD = "inventory.aprobar_solicitud"
LEER_SOLICITUDES_EXTERNAS = "inventory.leer_solicitudes_externas"
LIBERAR_RESERVA = "inventory.liberar_reserva"
# Permisos ya sembrados desde el slice 1, sin uso hasta ahora.
TRANSFERIR = "inventory.transferir"
RECEPCION = "inventory.recepcion"
# La guía la emite el área de almacén (RN-GDR-002), no quien despacha ni
# quien factura: permiso propio.
EMITIR_GUIA = "inventory.emitir_guia"


def _xlsx(contenido: bytes, nombre: str) -> Response:
    """Una planilla como descarga. El `Content-Disposition` es lo que le da
    nombre al archivo en el navegador; sin él baja como binario anónimo."""
    return Response(
        content=contenido,
        media_type=planilla.MIME,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


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
        # `exclude_none`: los roles que no se configuraron no se guardan como
        # `null`, se **ausentan**, que es lo que los hace heredar de la madre.
        asiento_contable_config=(
            body.asiento_contable_config.model_dump(exclude_none=True)
            if body.asiento_contable_config is not None
            else None
        ),
        frecuencia_conteo=body.frecuencia_conteo,
        padre_id=body.padre_id,
    )
    session.commit()
    return cat


@router.patch("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def editar_categoria(
    categoria_id: uuid.UUID,
    body: schemas.CategoriaUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Acá se configura cada cuánto se cuenta la categoría (RN-INV-007) y a
    qué cuentas del PCGE se imputa lo que agrupa (ADR-086)."""
    exigir_categoria(session, categoria_id, tenant)
    campos = body.model_dump()
    if body.asiento_contable_config is not None:
        campos["asiento_contable_config"] = body.asiento_contable_config.model_dump(
            exclude_none=True
        )
    cat = catalogo.editar_categoria(session, categoria_id, **campos)
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


@router.get("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def obtener_categoria(
    categoria_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Destino de `inventory.conteo_vencido`. Sin colisión con
    `/categorias-udm`: el path param va tipado `uuid.UUID`."""
    return exigir_categoria(session, categoria_id, tenant)


@router.get("/unidades-medida", response_model=list[schemas.UnidadMedidaOut])
def listar_unidades_medida(
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Lo necesita cualquier pantalla que teclee una cantidad: los decimales
    del campo salen de acá, no de una constante del frontend (RN-GER-010)."""
    return catalogo.listar_unidades_medida(session)


@router.post(
    "/unidades-medida", response_model=schemas.UnidadMedidaOut, status_code=201
)
def crear_unidad_medida(
    body: schemas.UnidadMedidaCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    unidad = catalogo.crear_unidad_medida(session, **body.model_dump())
    session.commit()
    return unidad


@router.patch("/unidades-medida/{unidad_medida_id}", response_model=schemas.UnidadMedidaOut)
def editar_unidad_medida(
    unidad_medida_id: uuid.UUID,
    body: schemas.UnidadMedidaUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    unidad = catalogo.editar_unidad_medida(session, unidad_medida_id, **body.model_dump())
    session.commit()
    return unidad


@router.get("/categorias-udm", response_model=list[schemas.CategoriaUdmOut])
def listar_categorias_udm(
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return catalogo.listar_categorias_udm(session)


@router.post(
    "/categorias-udm", response_model=schemas.CategoriaUdmOut, status_code=201
)
def crear_categoria_udm(
    body: schemas.CategoriaUdmCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    categoria = catalogo.crear_categoria_udm(session, **body.model_dump())
    session.commit()
    return categoria


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
        dias_alerta_vencimiento=body.dias_alerta_vencimiento,
    )
    session.commit()
    return art


@router.get("/articulos", response_model=Pagina[schemas.ArticuloOut])
def listar_articulos(
    empresa_id: uuid.UUID | None = None,
    tipo: list[str] | None = Query(
        None, description="Filtra por tipo de artículo; repetible (`?tipo=a&tipo=b`)"
    ),
    q: str | None = Query(None, description="Busca en el nombre y el código interno"),
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session,
        catalogo.q_articulos(session, tenant.filtro_empresa(empresa_id), tipo, q),
        p,
    )


# Las tres rutas literales van **antes** de `/articulos/{articulo_id}`:
# FastAPI resuelve por orden y "plantilla" entraría como un id que no es UUID.
@router.get("/articulos/plantilla")
def descargar_plantilla_articulos(
    _: Usuario = Depends(require_permission(CATALOGO)),
):
    """La hoja que se llena para cargar el catálogo de golpe (RN-INV-023)."""
    return _xlsx(importacion_articulos.plantilla(), "plantilla-articulos.xlsx")


@router.get("/articulos/exportar")
def exportar_articulos(
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El catálogo en la misma plantilla, con los datos adentro (ADR-052)."""
    return _xlsx(
        importacion_articulos.exportar(session, empresa_id=tenant.empresa()),
        "articulos.xlsx",
    )


@router.post("/articulos/importar/validar", response_model=schemas.RevisionArticulosOut)
async def validar_importacion_articulos(
    archivo: UploadFile,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Dice qué entra, qué actualiza y qué no. **No guarda nada.**"""
    return importacion_articulos.validar(
        session,
        empresa_id=tenant.empresa(),
        contenido=await archivo.read(),
    )


@router.post(
    "/articulos/importar",
    status_code=201,
    response_model=schemas.ResultadoImportacionOut,
)
def importar_articulos(
    body: schemas.ImportarArticulosIn,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Crea y actualiza lo que la pantalla confirmó, revalidando todo."""
    resultado = importacion_articulos.importar(
        session,
        empresa_id=tenant.empresa(),
        articulos=[a.model_dump() for a in body.articulos],
    )
    session.commit()
    return resultado


@router.get("/articulos/{articulo_id}", response_model=schemas.ArticuloOut)
def obtener_articulo(
    articulo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_articulo(session, articulo_id, tenant)


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
@router.get("/skus", response_model=list[schemas.SkuListadoOut])
def listar_skus(
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Qué se puede mover: lo consume el formulario de devolución y cualquier
    pantalla que pregunte por un SKU concreto."""
    return catalogo.listar_skus(session, tenant.filtro_empresa())


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


@router.get("/skus/{sku_id}", response_model=schemas.SkuDetalleOut)
def obtener_sku(
    sku_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Destino de `inventory.stock_bajo_minimo`: el SKU, su artículo y su
    saldo en cada almacén, que es lo que hay que mirar para decidir reponer."""
    exigir_sku(session, sku_id, tenant)
    return stock_uc.detalle_sku(session, sku_id)


# --- Stock / movimientos ----------------------------------------------------
@router.get("/stock", response_model=Pagina[schemas.StockOut])
def consultar_stock(
    almacen_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    categoria_id: uuid.UUID | None = None,
    bajo_minimo: bool = False,
    q: str | None = Query(default=None, max_length=100),
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Qué hay y dónde. Los filtros son los de la pantalla de stock: por
    almacén, por sucursal (todos sus almacenes), por categoría, solo lo que
    está bajo su punto de reorden, o por texto sobre el artículo y el SKU."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return stock_uc.consultar_stock_pagina(
        session,
        p,
        almacen_id,
        tenant.filtro_empresa(),
        sucursal_id=sucursal_id,
        categoria_id=categoria_id,
        bajo_minimo=bajo_minimo,
        texto=q,
    )


@router.get("/movimientos", response_model=Pagina[schemas.MovimientoKardexOut])
def consultar_movimientos(
    almacen_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """El kardex. `movimiento_inventario` se escribe desde el primer slice y
    hasta ahora no había forma de leerlo: la pantalla decía cuánto queda y
    nunca por qué cambió."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    if sku_id is not None:
        exigir_sku(session, sku_id, tenant)
    return stock_uc.consultar_movimientos_pagina(
        session,
        p,
        almacen_id=almacen_id,
        sku_id=sku_id,
        empresa_id=tenant.filtro_empresa(),
    )


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
            motivo_lote=body.motivo_lote,
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
    actor: Usuario = Depends(require_permission(MOVIMIENTO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Barrido de vencidos: bloquea y publica `inventory.lote_vencido_detectado`.
    El picking ya lo hace al tocar cada lote; esto lo adelanta a demanda."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    bloqueados = lotes_uc.bloquear_vencidos(
        session, almacen_id, tenant.filtro_empresa(), usuario_id=actor.id
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


# Después de `/lotes/bloquear-vencidos`: FastAPI resuelve en orden de
# declaración y un path param `uuid.UUID` declarado antes se quedaría con la
# ruta literal y respondería 422 en vez de dejarla pasar.
@router.get("/lotes/{lote_id}", response_model=schemas.LoteDetalleOut)
def obtener_lote(
    lote_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Destino de `inventory.lote_vencido_detectado`: el reporte dice que se
    bloqueó, esto dice cuánto quedó bloqueado y en qué almacén."""
    exigir_lote(session, lote_id, tenant)
    return lotes_uc.detalle(session, lote_id, empresa_id=tenant.filtro_empresa())


# --- Reservas ---------------------------------------------------------------
@router.get("/reservas", response_model=list[schemas.ReservaOut])
def listar_reservas(
    almacen_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Reservas activas — lo que ya está prometido y por eso no figura en
    el `disponible` de `GET /stock` (RN-INV-009)."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return reservas_uc.listar(
        session,
        almacen_id=almacen_id,
        sku_id=sku_id,
        empresa_id=tenant.filtro_empresa(),
    )


@router.post("/reservas/{reserva_id}/liberar", response_model=schemas.ReservaOut)
def liberar_reserva(
    reserva_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(LIBERAR_RESERVA)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Liberación manual ante desabastecimiento o sobredemanda: el central
    suelta lo prometido a uno para redistribuirlo (RN-INV-011)."""
    exigir_reserva(session, reserva_id, tenant)
    reserva = reservas_uc.liberar(session, reserva_id, actor.id)
    session.commit()
    return reserva


# --- Solicitud de insumos ---------------------------------------------------
@router.post("/solicitudes", response_model=schemas.SolicitudOut, status_code=201)
def crear_solicitud(
    body: schemas.SolicitudCreate,
    actor: Usuario = Depends(require_permission(SOLICITAR_INSUMOS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_almacen(session, body.almacen_solicitante_id, tenant)
    if body.almacen_abastecedor_id is not None:
        exigir_almacen(session, body.almacen_abastecedor_id, tenant)
    solicitud = solicitudes_uc.crear_solicitud(
        session,
        almacen_solicitante_id=body.almacen_solicitante_id,
        almacen_abastecedor_id=body.almacen_abastecedor_id,
        items=[(i.sku_id, i.cantidad) for i in body.items],
        solicitado_por=actor.id,
        observacion=body.observacion,
    )
    session.commit()
    return solicitud


@router.get("/solicitudes", response_model=Pagina[schemas.SolicitudOut])
def listar_solicitudes(
    almacen_solicitante_id: uuid.UUID | None = None,
    estado: str | None = None,
    sucursal_id: uuid.UUID | None = None,
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Los borradores no aparecen acá salvo pidiendo `estado=borrador`: una
    lista que nadie envió todavía no le pidió nada a nadie."""
    if almacen_solicitante_id is not None:
        exigir_almacen(session, almacen_solicitante_id, tenant)
    return paginar(
        session,
        solicitudes_uc.q_listar(
            session,
            almacen_solicitante_id=almacen_solicitante_id,
            estado=estado,
            empresa_id=tenant.filtro_empresa(),
            sucursal_id=sucursal_id,
            marca_id=marca_id,
        ),
        p,
    )


@router.get(
    "/solicitudes/resumen", response_model=list[schemas.SolicitudResumenOut]
)
def resumen_solicitudes(
    desde: date | None = None,
    hasta: date | None = None,
    limit: int = 50,
    _: Usuario = Depends(require_permission(LEER_SOLICITUDES_EXTERNAS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Qué artículos y sucursales piden más (contrato público, ver
    `docs/architecture/events.md`) — insumo de `purchases` para negociar
    volumen con proveedores."""
    return queries_publicas.solicitudes_resumen_para_negociacion(
        session, tenant.filtro_empresa(), desde=desde, hasta=hasta, limit=limit
    )


def _detalle_solicitud(
    session: Session, solicitud_id: uuid.UUID
) -> schemas.SolicitudDetalleOut:
    solicitud, items = solicitudes_uc.detalle(session, solicitud_id)
    return schemas.SolicitudDetalleOut(
        **schemas.SolicitudOut.model_validate(solicitud).model_dump(),
        items=[schemas.SolicitudItemOut.model_validate(i) for i in items],
    )


# `/solicitudes/borrador` va antes que `/solicitudes/{solicitud_id}`: si no,
# FastAPI intenta leer "borrador" como UUID (mismo motivo que en conteos).
@router.get(
    "/solicitudes/borrador", response_model=schemas.SolicitudDetalleOut
)
def borrador_de_solicitud(
    almacen_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(SOLICITAR_INSUMOS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El requerimiento de la jornada de ese almacén, listo para editar.

    La crea si no existe, ya cargada con lo que está bajo mínimo, y si ya
    existía le suma lo que cayó desde la última vez (RN-INV-023). Es lo que
    hay detrás del botón: el personal no arma la lista desde cero.
    """
    exigir_almacen(session, almacen_id, tenant)
    borrador = solicitudes_uc.borrador_del_almacen(
        session, almacen_id=almacen_id, usuario_id=actor.id
    )
    session.commit()
    return _detalle_solicitud(session, borrador.id)


@router.post(
    "/solicitudes/{solicitud_id}/items",
    response_model=schemas.SolicitudDetalleOut,
    status_code=201,
)
def agregar_item_solicitud(
    solicitud_id: uuid.UUID,
    body: schemas.SolicitudItemAgregarIn,
    _: Usuario = Depends(require_permission(SOLICITAR_INSUMOS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Lo que el local decide pedir sin que el stock lo pida. Queda marcado
    como no urgente si el SKU no estaba bajo mínimo (RN-INV-024)."""
    exigir_solicitud(session, solicitud_id, tenant)
    solicitudes_uc.agregar_item(
        session, solicitud_id, sku_id=body.sku_id, cantidad=body.cantidad
    )
    session.commit()
    return _detalle_solicitud(session, solicitud_id)


@router.patch(
    "/solicitudes/{solicitud_id}/items/{sku_id}",
    response_model=schemas.SolicitudDetalleOut,
)
def cambiar_item_solicitud(
    solicitud_id: uuid.UUID,
    sku_id: uuid.UUID,
    body: schemas.SolicitudItemCantidadIn,
    _: Usuario = Depends(require_permission(SOLICITAR_INSUMOS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_solicitud(session, solicitud_id, tenant)
    solicitudes_uc.cambiar_cantidad(
        session, solicitud_id, sku_id=sku_id, cantidad=body.cantidad
    )
    session.commit()
    return _detalle_solicitud(session, solicitud_id)


@router.delete(
    "/solicitudes/{solicitud_id}/items/{sku_id}",
    response_model=schemas.SolicitudDetalleOut,
)
def quitar_item_solicitud(
    solicitud_id: uuid.UUID,
    sku_id: uuid.UUID,
    _: Usuario = Depends(require_permission(SOLICITAR_INSUMOS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_solicitud(session, solicitud_id, tenant)
    solicitudes_uc.quitar_item(session, solicitud_id, sku_id=sku_id)
    session.commit()
    return _detalle_solicitud(session, solicitud_id)


@router.post(
    "/solicitudes/{solicitud_id}/enviar", response_model=schemas.SolicitudOut
)
def enviar_solicitud(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(SOLICITAR_INSUMOS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El borrador pasa a `pendiente` y recién ahí espera aprobación."""
    exigir_solicitud(session, solicitud_id, tenant)
    solicitud = solicitudes_uc.enviar_borrador(session, solicitud_id, actor.id)
    session.commit()
    return solicitud


@router.get(
    "/solicitudes/{solicitud_id}", response_model=schemas.SolicitudDetalleOut
)
def ver_solicitud(
    solicitud_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_solicitud(session, solicitud_id, tenant)
    return _detalle_solicitud(session, solicitud_id)


@router.post(
    "/solicitudes/{solicitud_id}/aprobar", response_model=schemas.SolicitudOut
)
def aprobar_solicitud(
    solicitud_id: uuid.UUID,
    body: schemas.SolicitudAprobar,
    actor: Usuario = Depends(require_permission(APROBAR_SOLICITUD)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Aprobar reserva el stock en el abastecedor: entre la aprobación y el
    picking pasan horas y sin reserva otra sucursal se lleva lo mismo."""
    exigir_solicitud(session, solicitud_id, tenant)
    solicitud = solicitudes_uc.aprobar_solicitud(
        session,
        solicitud_id,
        actor.id,
        {a.sku_id: a.cantidad for a in body.aprobadas},
    )
    session.commit()
    return solicitud


@router.post(
    "/solicitudes/{solicitud_id}/rechazar", response_model=schemas.SolicitudOut
)
def rechazar_solicitud(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(APROBAR_SOLICITUD)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_solicitud(session, solicitud_id, tenant)
    solicitud = solicitudes_uc.rechazar_solicitud(session, solicitud_id, actor.id)
    session.commit()
    return solicitud


@router.post(
    "/solicitudes/{solicitud_id}/cancelar", response_model=schemas.SolicitudOut
)
def cancelar_solicitud(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(SOLICITAR_INSUMOS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cancelar libera las reservas que la aprobación había tomado
    (RN-INV-010)."""
    exigir_solicitud(session, solicitud_id, tenant)
    solicitud = solicitudes_uc.cancelar_solicitud(session, solicitud_id, actor.id)
    session.commit()
    return solicitud


# --- Transferencias ---------------------------------------------------------
@router.post(
    "/transferencias", response_model=schemas.TransferenciaOut, status_code=201
)
def despachar_transferencia(
    body: schemas.TransferenciaCreate,
    actor: Usuario = Depends(require_permission(TRANSFERIR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Descuenta el origen y deja el stock `en_transito` (RN-INV-003). Con
    `solicitud_id` despacha lo aprobado; sin él es transferencia lateral y
    los ítems son obligatorios."""
    exigir_almacen(session, body.origen_almacen_id, tenant)
    exigir_almacen(session, body.destino_almacen_id, tenant)
    if body.solicitud_id is not None:
        exigir_solicitud(session, body.solicitud_id, tenant)
    transferencia = transferencias_uc.despachar(
        session,
        origen_almacen_id=body.origen_almacen_id,
        destino_almacen_id=body.destino_almacen_id,
        despachado_por=actor.id,
        solicitud_id=body.solicitud_id,
        items=[(i.sku_id, i.cantidad) for i in body.items] or None,
        transportista_id=body.transportista_id,
        observacion=body.observacion,
    )
    session.commit()
    return transferencia


@router.get("/transferencias", response_model=Pagina[schemas.TransferenciaOut])
def listar_transferencias(
    almacen_id: uuid.UUID | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """`almacen_id` matchea origen o destino: lo que sale y lo que llega."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return paginar(
        session,
        transferencias_uc.q_listar(
            session,
            almacen_id=almacen_id,
            estado=estado,
            empresa_id=tenant.filtro_empresa(),
        ),
        p,
    )


@router.get(
    "/transferencias/{transferencia_id}",
    response_model=schemas.TransferenciaDetalleOut,
)
def ver_transferencia(
    transferencia_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_transferencia(session, transferencia_id, tenant)
    transferencia, items = transferencias_uc.detalle(session, transferencia_id)
    return schemas.TransferenciaDetalleOut(
        **schemas.TransferenciaOut.model_validate(transferencia).model_dump(),
        items=[schemas.TransferenciaItemOut.model_validate(i) for i in items],
    )


@router.post(
    "/transferencias/{transferencia_id}/recibir",
    response_model=schemas.TransferenciaDetalleOut,
)
def recibir_transferencia(
    transferencia_id: uuid.UUID,
    body: schemas.TransferenciaRecibir,
    actor: Usuario = Depends(require_permission(RECEPCION)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Ingresa al destino lo que llegó, lote por lote. Una diferencia
    contra lo enviado no se corrige sola: queda auditable (RN-INV-002).

    Con `parcial: true` entra solo lo declarado y el resto sigue en
    tránsito: el camión que trae la mitad hoy y la otra mitad mañana."""
    exigir_transferencia(session, transferencia_id, tenant)
    transferencias_uc.recibir(
        session,
        transferencia_id,
        actor.id,
        {i.item_id: i.cantidad for i in body.items},
        parcial=body.parcial,
    )
    transferencia, items = transferencias_uc.detalle(session, transferencia_id)
    session.commit()
    return schemas.TransferenciaDetalleOut(
        **schemas.TransferenciaOut.model_validate(transferencia).model_dump(),
        items=[schemas.TransferenciaItemOut.model_validate(i) for i in items],
    )


# --- Guía de remisión (RN-GDR-001..003, RN-TRP-002) --------------------------
@router.post(
    "/transferencias/{transferencia_id}/guia",
    response_model=schemas.GuiaRemisionDetalleOut,
    status_code=201,
)
def emitir_guia(
    transferencia_id: uuid.UUID,
    body: schemas.GuiaRemisionCreate,
    actor: Usuario = Depends(require_permission(EMITIR_GUIA)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Emite la guía del traslado. Los bienes declarados salen de la
    transferencia, no del request (RN-TRP-002): lo que viaja tiene que ser
    exactamente lo que se descontó del origen.

    Idempotente por transferencia — pedirla dos veces devuelve la misma
    guía, porque dos guías del mismo traslado declaran la misma mercadería
    dos veces.
    """
    exigir_transferencia(session, transferencia_id, tenant)
    guia = guias_uc.emitir_guia(
        session,
        transferencia_id,
        emitida_por=actor.id,
        **body.model_dump(),
    )
    session.commit()
    # Después del commit: el worker corre en otro proceso y solo ve filas ya
    # confirmadas.
    inventory_tasks.encolar(guia.id)
    guia, items = guias_uc.detalle(session, guia.id)
    return schemas.GuiaRemisionDetalleOut(
        **schemas.GuiaRemisionOut.model_validate(guia).model_dump(),
        items=[schemas.GuiaRemisionItemOut.model_validate(i) for i in items],
    )


@router.get(
    "/transferencias/{transferencia_id}/guia",
    response_model=schemas.GuiaRemisionDetalleOut,
)
def ver_guia_de_transferencia(
    transferencia_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_transferencia(session, transferencia_id, tenant)
    guia = guias_uc.de_transferencia(session, transferencia_id)
    guia, items = guias_uc.detalle(session, guia.id)
    return schemas.GuiaRemisionDetalleOut(
        **schemas.GuiaRemisionOut.model_validate(guia).model_dump(),
        items=[schemas.GuiaRemisionItemOut.model_validate(i) for i in items],
    )


@router.get("/guias-remision", response_model=Pagina[schemas.GuiaRemisionOut])
def listar_guias(
    estado_emision: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Las guías de la empresa. `estado_emision=rechazado` es la bandeja que
    de verdad hay que mirar: una guía rechazada por SUNAT hay que
    corregirla y reemitirla."""
    return paginar(
        session,
        guias_uc.q_listar(
            session,
            empresa_id=tenant.filtro_empresa(),
            estado_emision=estado_emision,
        ),
        p,
    )


# --- Conteo cíclico ---------------------------------------------------------
# `/conteos/programa` y `/conteos/verificar-vencidos` van antes que
# `/conteos/{conteo_id}`: si no, FastAPI intenta leer "programa" como UUID.
@router.get("/conteos/programa", response_model=list[schemas.ProgramaConteoOut])
def programa_conteos(
    almacen_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Calendario derivado del último conteo cerrado + la frecuencia de cada
    categoría (RN-INV-007). Los vencidos salen primero."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return conteos_uc.programa(
        session,
        almacen_id=almacen_id,
        empresa_id=tenant.filtro_empresa(),
        sucursal_id=sucursal_id,
        marca_id=marca_id,
    )


@router.post(
    "/conteos/verificar-vencidos", response_model=list[schemas.ProgramaConteoOut]
)
def verificar_conteos_vencidos(
    almacen_id: uuid.UUID | None = None,
    actor: Usuario = Depends(require_permission(CONTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Reporta a almacén y gerencia lo que no se contó en su fecha
    (RN-INV-021): publica `inventory.conteo_vencido` por cada uno."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return conteos_uc.reportar_vencidos(
        session,
        almacen_id=almacen_id,
        empresa_id=tenant.filtro_empresa(),
        usuario_id=actor.id,
    )


@router.post("/conteos", response_model=schemas.ConteoOut, status_code=201)
def abrir_conteo(
    body: schemas.ConteoCreate,
    actor: Usuario = Depends(require_permission(CONTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_almacen(session, body.almacen_id, tenant)
    if body.categoria_id is not None:
        exigir_categoria(session, body.categoria_id, tenant)
    conteo = conteos_uc.abrir_conteo(
        session,
        almacen_id=body.almacen_id,
        categoria_id=body.categoria_id,
        tipo=body.tipo,
        abierto_por=actor.id,
        observacion=body.observacion,
    )
    session.commit()
    return conteo


@router.get("/conteos", response_model=Pagina[schemas.ConteoOut])
def listar_conteos(
    almacen_id: uuid.UUID | None = None,
    estado: str | None = None,
    sucursal_id: uuid.UUID | None = None,
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Los conteos del almacén, sucursal o marca, con el abierto primero.

    Faltaba: hasta ahora un conteo solo se podía pedir por su id, o sea
    sabiéndolo de antemano, y ninguna pantalla podía ofrecer "seguir
    contando lo que quedó abierto".
    """
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return paginar(
        session,
        conteos_uc.q_listar(
            session,
            almacen_id=almacen_id,
            estado=estado,
            empresa_id=tenant.filtro_empresa(),
            sucursal_id=sucursal_id,
            marca_id=marca_id,
        ),
        p,
    )


@router.get("/conteos/{conteo_id}", response_model=schemas.ConteoDetalleOut)
def ver_conteo(
    conteo_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(CONTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Conteo "a ciegas" por defecto: el stock esperado y la diferencia solo
    viajan a quien tiene `inventory.ver_stock_esperado` (RN-INV-005)."""
    exigir_conteo(session, conteo_id, tenant)
    conteo, items = conteos_uc.detalle(session, conteo_id)
    ve_esperado = tiene_permiso(session, actor, VER_ESPERADO)
    return schemas.ConteoDetalleOut(
        **schemas.ConteoOut.model_validate(conteo).model_dump(),
        items=[
            schemas.ConteoItemOut(
                sku_id=item.sku_id,
                cantidad_contada=item.cantidad_contada,
                cantidad_sistema=item.cantidad_sistema if ve_esperado else None,
                diferencia=item.diferencia if ve_esperado else None,
            )
            for item in items
        ],
    )


@router.post("/conteos/{conteo_id}/cantidades", response_model=schemas.ConteoOut)
def registrar_cantidades(
    conteo_id: uuid.UUID,
    body: schemas.ConteoCantidades,
    _: Usuario = Depends(require_permission(CONTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_conteo(session, conteo_id, tenant)
    conteo = conteos_uc.registrar_cantidades(
        session, conteo_id, [(i.sku_id, i.cantidad) for i in body.items]
    )
    session.commit()
    return conteo


@router.post("/conteos/{conteo_id}/cerrar", response_model=schemas.ConteoCierreOut)
def cerrar_conteo(
    conteo_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(CONTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cierra y solicita un ajuste por cada diferencia. No mueve stock: los
    ajustes nacen `pendiente` y los aprueba otro usuario (RN-INV-006)."""
    exigir_conteo(session, conteo_id, tenant)
    conteo, generados = conteos_uc.cerrar_conteo(session, conteo_id, actor.id)
    session.commit()
    return schemas.ConteoCierreOut(conteo=conteo, ajustes=generados)


@router.post("/conteos/{conteo_id}/anular", response_model=schemas.ConteoOut)
def anular_conteo(
    conteo_id: uuid.UUID,
    body: schemas.ConteoAnulacion,
    actor: Usuario = Depends(require_permission(CONTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Descarta un conteo abierto por error, sin generar ajustes ni poner al
    día el calendario de la categoría. Exige motivo."""
    exigir_conteo(session, conteo_id, tenant)
    conteo = conteos_uc.anular_conteo(session, conteo_id, actor.id, body.motivo)
    session.commit()
    return conteo


# --- Ajustes (segregación solicitar/aprobar) --------------------------------
@router.get("/ajustes", response_model=Pagina[schemas.AjusteOut])
def listar_ajustes(
    almacen_id: uuid.UUID | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Los ajustes se solicitaban y se aprobaban a ciegas: no había forma de
    listar los pendientes. `inventory.ajuste_fuera_margen` reportaba un hecho
    que no se podía ir a mirar."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return paginar(
        session,
        ajustes.q_ajustes(
            session, tenant.filtro_empresa(), almacen_id=almacen_id, estado=estado
        ),
        p,
    )


@router.get("/ajustes/{ajuste_id}", response_model=schemas.AjusteDetalleOut)
def obtener_ajuste(
    ajuste_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Destino de `inventory.ajuste_fuera_margen`, y donde se decide si se
    aprueba o se rechaza."""
    exigir_ajuste(session, ajuste_id, tenant)
    return ajustes.detalle_ajuste(session, ajuste_id)


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
        lote_codigo=body.lote_codigo,
        fecha_vencimiento=body.fecha_vencimiento,
        fecha_elaboracion=body.fecha_elaboracion,
        condicion_almacenamiento=body.condicion_almacenamiento,
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


# --- Recetas ----------------------------------------------------------------
@router.post("/recetas", response_model=schemas.RecetaOut, status_code=201)
def crear_receta(
    body: schemas.RecetaCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    datos = body.model_dump()
    receta = recetas_uc.crear_receta(
        session, empresa_id=tenant.empresa(datos.pop("empresa_id")), **datos
    )
    session.commit()
    return recetas_uc.detalle_receta(session, receta.id)


@router.get("/recetas", response_model=list[schemas.RecetaOut])
def listar_recetas(
    tipo: str | None = None,
    categoria_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """`tipo` es `subreceta` (produce un artículo) o `producto` (se vende);
    se deriva de `articulo_id`, no hay columna que mantener (RN-COM-030)."""
    return recetas_uc.listar_recetas(
        session, tenant.filtro_empresa(), tipo=tipo, categoria_id=categoria_id
    )


@router.get("/recetas/matriz", response_model=schemas.MatrizOut)
def ver_matriz_recetas(
    receta_ids: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El recetario en grilla: insumos en las filas, recetas en las columnas.

    Declarada **antes** de `/recetas/{receta_id}` por lo mismo que la
    plantilla: FastAPI resuelve por orden y "matriz" entraría como un
    `receta_id` que no es UUID.

    `receta_ids` es una lista separada por comas. Sin ella viene el recetario
    entero, que es lo que quiere quien abre la pantalla a buscar; filtrar es
    lo que quiere quien ya sabe qué comparar.
    """
    ids = (
        [uuid.UUID(x) for x in receta_ids.split(",") if x.strip()]
        if receta_ids
        else None
    )
    return matriz_uc.grilla(
        session, empresa_id=tenant.empresa_id, receta_ids=ids
    )


@router.put("/recetas/matriz", response_model=schemas.GuardarMatrizOut)
def guardar_matriz_recetas(
    body: schemas.GuardarMatrizIn,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Aplica las celdas que cambiaron, cada una en su propio SAVEPOINT.

    Devuelve qué pasó con cada una en vez de un 409 al primer problema:
    pegar cuarenta celdas y perderlas todas porque una tenía un insumo mal
    escrito es el modo de falla que hace que nadie vuelva a pegar nada
    (mismo criterio que ADR-046 con las recetas).
    """
    resultado = matriz_uc.guardar(
        session,
        empresa_id=tenant.empresa_id,
        celdas=[c.model_dump() for c in body.celdas],
    )
    session.commit()
    return resultado


@router.get("/recetas/plantilla")
def descargar_plantilla_recetas(
    _: Usuario = Depends(require_permission(CATALOGO)),
):
    """La hoja que se llena para cargar el recetario de golpe (RN-COM-031).

    Declarada **antes** de `/recetas/{receta_id}`: FastAPI resuelve por orden
    y "plantilla" entraría como un `receta_id` que no es UUID.
    """
    return _xlsx(importacion_recetas.plantilla(), "plantilla-recetas.xlsx")


@router.get("/recetas/exportar")
def exportar_recetas(
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El recetario en la misma plantilla, con los datos adentro (ADR-052).

    Pide permiso de **lectura**: son los mismos datos que devuelve el listado,
    solo empaquetados en un archivo.
    """
    return _xlsx(
        importacion_recetas.exportar(session, empresa_id=tenant.empresa()),
        "recetas.xlsx",
    )


@router.post("/recetas/importar/validar", response_model=schemas.RevisionRecetasOut)
async def validar_importacion_recetas(
    archivo: UploadFile,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Dice qué entra, qué actualiza y qué no. **No guarda nada** — la pantalla
    resuelve los insumos que el catálogo no reconoce y recién ahí se importa."""
    return importacion_recetas.validar(
        session,
        empresa_id=tenant.empresa(),
        contenido=await archivo.read(),
    )


@router.post(
    "/recetas/importar",
    status_code=201,
    response_model=schemas.ResultadoImportacionOut,
)
def importar_recetas(
    body: schemas.ImportarRecetasIn,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Crea lo que la pantalla confirmó, revalidando todo: lo que llega es un
    JSON que el cliente pudo editar."""
    resultado = importacion_recetas.importar(
        session,
        empresa_id=tenant.empresa(),
        recetas=[r.model_dump() for r in body.recetas],
    )
    session.commit()
    return resultado


@router.get("/recetas/{receta_id}", response_model=schemas.RecetaDetalleOut)
def ver_receta(
    receta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_receta(session, receta_id, tenant)
    return recetas_uc.detalle_receta(session, receta_id)


@router.patch("/recetas/{receta_id}", response_model=schemas.RecetaDetalleOut)
def editar_receta(
    receta_id: uuid.UUID,
    body: schemas.RecetaUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_receta(session, receta_id, tenant)
    recetas_uc.editar_receta(session, receta_id, **body.model_dump())
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


@router.delete("/recetas/{receta_id}", status_code=204)
def eliminar_receta(
    receta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Borra la receta y sus líneas. Responde 409 si algún producto comercial
    la usa, nombrándolo: sin receta ese producto no se podría preparar."""
    exigir_receta(session, receta_id, tenant)
    recetas_uc.eliminar_receta(session, receta_id)
    session.commit()


@router.post("/recetas/{receta_id}/duplicar", response_model=schemas.RecetaDetalleOut,
             status_code=201)
def duplicar_receta(
    receta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Clona la receta con sufijo "(copy)" para editarla desde ahí en vez de
    volver a teclear 15 insumos."""
    exigir_receta(session, receta_id, tenant)
    copia = recetas_uc.duplicar_receta(session, receta_id)
    session.commit()
    return recetas_uc.detalle_receta(session, copia.id)


@router.post("/recetas/{receta_id}/escalar", response_model=schemas.RecetaDetalleOut)
def escalar_receta(
    receta_id: uuid.UUID,
    body: schemas.RecetaEscalarIn,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Multiplica todas las cantidades por un factor, redondeando cada línea
    con los decimales de su propia unidad."""
    exigir_receta(session, receta_id, tenant)
    recetas_uc.escalar_receta(session, receta_id, body.factor)
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


@router.post("/recetas/{receta_id}/items", response_model=schemas.RecetaDetalleOut,
             status_code=201)
def agregar_item_receta(
    receta_id: uuid.UUID,
    body: schemas.RecetaItemCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_receta(session, receta_id, tenant)
    recetas_uc.agregar_item(session, receta_id, **body.model_dump())
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


@router.patch("/recetas/{receta_id}/items/{item_id}",
              response_model=schemas.RecetaDetalleOut)
def editar_item_receta(
    receta_id: uuid.UUID,
    item_id: uuid.UUID,
    body: schemas.RecetaItemUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_receta(session, receta_id, tenant)
    recetas_uc.editar_item(session, item_id, **body.model_dump())
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


@router.delete("/recetas/{receta_id}/items/{item_id}",
               response_model=schemas.RecetaDetalleOut)
def eliminar_item_receta(
    receta_id: uuid.UUID,
    item_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_receta(session, receta_id, tenant)
    recetas_uc.eliminar_item(session, item_id)
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


# --- Merma (RN-INV-012/017) ---------------------------------------------------
# Sin permisos nuevos: registrar merma es `solicitar_ajuste` y resolverla es
# `aprobar_ajuste`. La segregación que importa es la misma —quien declara que
# algo no sirve no firma su baja— y ya vive en los roles sembrados.
@router.post("/mermas", response_model=schemas.MermaOut, status_code=201)
def registrar_merma(
    body: schemas.MermaCreate,
    actor: Usuario = Depends(require_permission(SOLICITAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Aparta stock inservible. No lo saca del almacén: lo saca de la venta
    (RN-INV-012). El destino lo decide otro usuario al resolverla."""
    exigir_almacen(session, body.almacen_id, tenant)
    if body.lote_id is not None:
        exigir_lote(session, body.lote_id, tenant)
    reserva = merma_uc.registrar_merma(
        session,
        almacen_id=body.almacen_id,
        sku_id=body.sku_id,
        cantidad=body.cantidad,
        motivo=body.motivo,
        creado_por=actor.id,
        lote_id=body.lote_id,
    )
    session.commit()
    return reserva


@router.get("/mermas", response_model=list[schemas.MermaOut])
def listar_mermas(
    almacen_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Las pendientes de resolver: es la bandeja de la auditoría."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return merma_uc.listar_mermas(
        session, almacen_id=almacen_id, empresa_id=tenant.filtro_empresa()
    )


@router.post("/mermas/{reserva_id}/resolver", response_model=schemas.MermaOut)
def resolver_merma(
    reserva_id: uuid.UUID,
    body: schemas.MermaResolver,
    actor: Usuario = Depends(require_permission(APROBAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """`desecho` saca el stock y publica `inventory.merma_registrada` (que
    `accounting` asienta); `reintegro` lo devuelve a disponible."""
    exigir_reserva(session, reserva_id, tenant)
    reserva = merma_uc.resolver_merma(
        session, reserva_id, destino=body.destino, resuelto_por=actor.id
    )
    session.commit()
    return reserva


# --- Devoluciones (RN-INV-019/020) --------------------------------------------
@router.post("/devoluciones", response_model=schemas.DevolucionDetalleOut,
             status_code=201)
def registrar_devolucion(
    body: schemas.DevolucionCreate,
    actor: Usuario = Depends(require_permission(MOVIMIENTO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """A proveedor la mercadería sale; de cliente entra y `destino` decide
    si vuelve al estante o se aparta como merma."""
    exigir_almacen(session, body.almacen_id, tenant)
    devolucion = devoluciones_uc.registrar_devolucion(
        session,
        almacen_id=body.almacen_id,
        origen=body.origen,
        motivo=body.motivo,
        registrado_por=actor.id,
        items=[i.model_dump() for i in body.items],
        referencia_id=body.referencia_id,
        destino=body.destino,
        observacion=body.observacion,
    )
    devolucion, items = devoluciones_uc.detalle(session, devolucion.id)
    session.commit()
    return schemas.DevolucionDetalleOut(
        **schemas.DevolucionOut.model_validate(devolucion).model_dump(),
        items=[schemas.DevolucionItemOut.model_validate(i) for i in items],
    )


@router.get("/devoluciones", response_model=list[schemas.DevolucionOut])
def listar_devoluciones(
    almacen_id: uuid.UUID | None = None,
    origen: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return devoluciones_uc.listar(
        session,
        almacen_id=almacen_id,
        origen=origen,
        empresa_id=tenant.filtro_empresa(),
    )


@router.get("/devoluciones/{devolucion_id}",
            response_model=schemas.DevolucionDetalleOut)
def ver_devolucion(
    devolucion_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_devolucion(session, devolucion_id, tenant)
    devolucion, items = devoluciones_uc.detalle(session, devolucion_id)
    return schemas.DevolucionDetalleOut(
        **schemas.DevolucionOut.model_validate(devolucion).model_dump(),
        items=[schemas.DevolucionItemOut.model_validate(i) for i in items],
    )


@router.post("/devoluciones/{devolucion_id}/anular",
             response_model=schemas.DevolucionOut)
def anular_devolucion(
    devolucion_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(MOVIMIENTO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Repone lo que movió con movimientos contrarios. No borra la fila: que
    alguien se equivocó también es parte del rastro."""
    exigir_devolucion(session, devolucion_id, tenant)
    devolucion = devoluciones_uc.anular_devolucion(session, devolucion_id, actor.id)
    session.commit()
    return devolucion


@router.post("/devoluciones/{devolucion_id}/guia-remision",
             response_model=schemas.GuiaRemisionOut, status_code=201)
def emitir_guia_de_devolucion(
    devolucion_id: uuid.UUID,
    body: schemas.GuiaDevolucionCreate,
    actor: Usuario = Depends(require_permission(EMITIR_GUIA)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """La mercadería que se le devuelve al proveedor viaja por la vía
    pública: SUNAT no distingue el motivo para exigir la guía."""
    exigir_devolucion(session, devolucion_id, tenant)
    guia = guias_uc.emitir_guia_de_devolucion(
        session, devolucion_id, emitida_por=actor.id, **body.model_dump()
    )
    session.commit()
    inventory_tasks.encolar(guia.id)
    return guia
