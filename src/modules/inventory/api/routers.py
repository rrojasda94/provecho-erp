"""Routers FastAPI del módulo inventory: catálogo, stock y ajustes.

Reusa las dependencias de auth/RBAC del módulo users (mecanismo transversal).
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.inventory.api import schemas
from src.modules.inventory.application import ajustes, catalogo, queries_publicas
from src.modules.inventory.application import conteos as conteos_uc
from src.modules.inventory.application import guias as guias_uc
from src.modules.inventory.application import lotes as lotes_uc
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
    exigir_lote,
    exigir_reserva,
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
        frecuencia_conteo=body.frecuencia_conteo,
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
    """Acá se configura cada cuánto se cuenta la categoría (RN-INV-007)."""
    exigir_categoria(session, categoria_id, tenant)
    cat = catalogo.editar_categoria(session, categoria_id, **body.model_dump())
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
    )
    session.commit()
    return art


@router.get("/articulos", response_model=Pagina[schemas.ArticuloOut])
def listar_articulos(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session, catalogo.q_articulos(session, tenant.filtro_empresa(empresa_id)), p
    )


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
@router.get("/stock", response_model=Pagina[schemas.StockOut])
def consultar_stock(
    almacen_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return stock_uc.consultar_stock_pagina(
        session, p, almacen_id, tenant.filtro_empresa()
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
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    if almacen_solicitante_id is not None:
        exigir_almacen(session, almacen_solicitante_id, tenant)
    return paginar(
        session,
        solicitudes_uc.q_listar(
            session,
            almacen_solicitante_id=almacen_solicitante_id,
            estado=estado,
            empresa_id=tenant.filtro_empresa(),
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
    solicitud, items = solicitudes_uc.detalle(session, solicitud_id)
    return schemas.SolicitudDetalleOut(
        **schemas.SolicitudOut.model_validate(solicitud).model_dump(),
        items=[schemas.SolicitudItemOut.model_validate(i) for i in items],
    )


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
    contra lo enviado no se corrige sola: queda auditable (RN-INV-002)."""
    exigir_transferencia(session, transferencia_id, tenant)
    transferencias_uc.recibir(
        session,
        transferencia_id,
        actor.id,
        {i.item_id: i.cantidad for i in body.items},
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
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Calendario derivado del último conteo cerrado + la frecuencia de cada
    categoría (RN-INV-007). Los vencidos salen primero."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return conteos_uc.programa(
        session, almacen_id=almacen_id, empresa_id=tenant.filtro_empresa()
    )


@router.post(
    "/conteos/verificar-vencidos", response_model=list[schemas.ProgramaConteoOut]
)
def verificar_conteos_vencidos(
    almacen_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(CONTAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Reporta a almacén y gerencia lo que no se contó en su fecha
    (RN-INV-021): publica `inventory.conteo_vencido` por cada uno."""
    if almacen_id is not None:
        exigir_almacen(session, almacen_id, tenant)
    return conteos_uc.reportar_vencidos(
        session, almacen_id=almacen_id, empresa_id=tenant.filtro_empresa()
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


# --- Recetas ----------------------------------------------------------------
@router.post("/recetas", response_model=schemas.RecetaOut, status_code=201)
def crear_receta(
    body: schemas.RecetaCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    receta = recetas_uc.crear_receta(session, **body.model_dump())
    session.commit()
    return recetas_uc.detalle_receta(session, receta.id)


@router.get("/recetas", response_model=list[schemas.RecetaOut])
def listar_recetas(
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return recetas_uc.listar_recetas(session)


@router.get("/recetas/{receta_id}", response_model=schemas.RecetaDetalleOut)
def ver_receta(
    receta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return recetas_uc.detalle_receta(session, receta_id)


@router.patch("/recetas/{receta_id}", response_model=schemas.RecetaDetalleOut)
def editar_receta(
    receta_id: uuid.UUID,
    body: schemas.RecetaUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    recetas_uc.editar_receta(session, receta_id, **body.model_dump())
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


@router.delete("/recetas/{receta_id}", status_code=204)
def eliminar_receta(
    receta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Borra la receta y sus líneas. Responde 409 si algún producto comercial
    la usa, nombrándolo: sin receta ese producto no se podría preparar."""
    recetas_uc.eliminar_receta(session, receta_id)
    session.commit()


@router.post("/recetas/{receta_id}/duplicar", response_model=schemas.RecetaDetalleOut,
             status_code=201)
def duplicar_receta(
    receta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Clona la receta con sufijo "(copy)" para editarla desde ahí en vez de
    volver a teclear 15 insumos."""
    copia = recetas_uc.duplicar_receta(session, receta_id)
    session.commit()
    return recetas_uc.detalle_receta(session, copia.id)


@router.post("/recetas/{receta_id}/escalar", response_model=schemas.RecetaDetalleOut)
def escalar_receta(
    receta_id: uuid.UUID,
    body: schemas.RecetaEscalarIn,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Multiplica todas las cantidades por un factor, redondeando cada línea
    con los decimales de su propia unidad."""
    recetas_uc.escalar_receta(session, receta_id, body.factor)
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


@router.post("/recetas/{receta_id}/items", response_model=schemas.RecetaDetalleOut,
             status_code=201)
def agregar_item_receta(
    receta_id: uuid.UUID,
    body: schemas.RecetaItemCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
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
    session: Session = Depends(get_db),
):
    recetas_uc.editar_item(session, item_id, **body.model_dump())
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)


@router.delete("/recetas/{receta_id}/items/{item_id}",
               response_model=schemas.RecetaDetalleOut)
def eliminar_item_receta(
    receta_id: uuid.UUID,
    item_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    recetas_uc.eliminar_item(session, item_id)
    session.commit()
    return recetas_uc.detalle_receta(session, receta_id)
