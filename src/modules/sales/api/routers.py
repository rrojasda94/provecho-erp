"""Routers FastAPI del módulo sales: venta, cobro y catálogo comercial."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.sales.api import schemas
from src.modules.sales.application import (
    catalogo,
    comprobantes,
    cumplimiento,
    precios,
    queries_publicas,
    tasks,
    ventas,
)
from src.modules.sales.application.scope import exigir_venta
from src.modules.sales.infrastructure.repositories import ComprobanteRepo
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Usuario
from src.shared.integrations.factiliza import FactilizaError

router = APIRouter(prefix="/sales", tags=["sales"])

CREAR = "sales.crear"
COBRAR = "sales.cobrar"
LEER = "sales.leer"
ANULAR = "sales.anular"
CATALOGO = "sales.gestionar_catalogo"
LEER_CLIENTES_EXTERNOS = "sales.leer_clientes_externos"
EMITIR = "sales.emitir_comprobante"
ENTREGAR = "sales.entregar_pedido"


# --- Venta ------------------------------------------------------------------
@router.post("/ventas", response_model=schemas.VentaOut, status_code=201)
def crear_venta(
    body: schemas.VentaCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
    venta = ventas.crear_venta(
        session,
        sucursal_id=body.sucursal_id,
        punto_venta_id=body.punto_venta_id,
        canal=body.canal,
        modalidad=body.modalidad,
        usuario_id=actor.id,
        idempotency_key=body.idempotency_key,
        items=[it.model_dump() for it in body.items],
        cliente_id=body.cliente_id,
        referencia_atencion=body.referencia_atencion,
        id=body.id,
    )
    session.commit()
    return venta


@router.get("/ventas/{venta_id}", response_model=schemas.VentaOut)
def ver_venta(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_venta(session, venta_id, tenant)


@router.post("/ventas/{venta_id}/pagos", response_model=schemas.PagoOut, status_code=201)
def registrar_pago(
    venta_id: uuid.UUID,
    body: schemas.PagoCreate,
    _: Usuario = Depends(require_permission(COBRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_venta(session, venta_id, tenant)
    pago, _venta, comprobante = ventas.registrar_pago(
        session,
        venta_id=venta_id,
        medio_pago_id=body.medio_pago_id,
        monto=body.monto,
        idempotency_key=body.idempotency_key,
        referencia_externa=body.referencia_externa,
        id=body.id,
    )
    session.commit()
    # Después del commit: el worker corre en otro proceso y solo puede ver
    # filas ya confirmadas.
    if comprobante is not None:
        tasks.encolar(comprobante.id)
    return pago


@router.post("/ventas/{venta_id}/anular", response_model=schemas.VentaOut)
def anular_venta(
    venta_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ANULAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_venta(session, venta_id, tenant)
    venta = ventas.anular_venta(session, venta_id, actor.id)
    session.commit()
    return venta


# --- Cumplimiento de pedido (PROC-OPE-002) ----------------------------------
@router.post("/ventas/{venta_id}/entrega", response_model=schemas.EntregaOut)
def registrar_entrega(
    venta_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ENTREGAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cierra el pedido: lo entrega al cliente y publica
    `sales.venta_entregada`. Permiso propio, distinto del avance de cocina
    (RN-CUP-006); repetirlo no reemite el evento (RN-CUP-005)."""
    exigir_venta(session, venta_id, tenant)
    resultado = cumplimiento.registrar_entrega(
        session, venta_id, entregado_por=actor.id
    )
    session.commit()
    return resultado


# --- Comprobante electrónico ------------------------------------------------
@router.get("/ventas/{venta_id}/comprobante", response_model=schemas.ComprobanteOut)
def ver_comprobante(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    comprobante = ComprobanteRepo(session).por_venta(venta_id)
    if comprobante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "la venta no tiene comprobante")
    return comprobante


@router.post(
    "/comprobantes/{comprobante_id}/reintentar",
    response_model=schemas.ComprobanteOut,
)


def reintentar_emision(
    comprobante_id: uuid.UUID,
    _: Usuario = Depends(require_permission(EMITIR)),
    session: Session = Depends(get_db),
):
    """Reenvía a SUNAT un comprobante rechazado o con fallo de transporte.
    Corre en línea (no en la cola) para devolver el veredicto al operador."""
    try:
        comprobante = comprobantes.emitir_comprobante(session, comprobante_id)
    except FactilizaError as e:
        # Commit en el camino de error: el intento ya quedó contado en la
        # fila y hay que persistirlo. Por eso este `except` sobrevive al
        # handler global — no solo traduce, decide sobre la transacción.
        session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    session.commit()
    return comprobante


# --- Contrato público de lectura (marketing/comercial/análisis) -------------
@router.get("/clientes", response_model=list[schemas.ClientePublicoOut])
def listar_clientes_publico(
    grupo_id: uuid.UUID,
    tipo: str | None = None,
    _: Usuario = Depends(require_permission(LEER_CLIENTES_EXTERNOS)),
    session: Session = Depends(get_db),
):
    return queries_publicas.listar_clientes_para_analisis(session, grupo_id, tipo=tipo)


# --- Catálogo comercial -----------------------------------------------------
@router.post("/productos", response_model=schemas.ProductoOut, status_code=201)
def crear_producto(
    body: schemas.ProductoCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    prod = catalogo.crear_producto(session, **body.model_dump())
    session.commit()
    return prod


@router.get("/productos", response_model=list[schemas.ProductoOut])
def listar_productos(
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return catalogo.listar_productos(session, marca_id)


@router.patch("/productos/{producto_id}", response_model=schemas.ProductoOut)
def editar_producto(
    producto_id: uuid.UUID,
    body: schemas.ProductoUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    prod = catalogo.editar_producto(session, producto_id, **body.model_dump())
    session.commit()
    return prod


@router.post("/medios-pago", response_model=schemas.MedioPagoOut, status_code=201)
def crear_medio_pago(
    body: schemas.MedioPagoCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    medio = catalogo.crear_medio_pago(session, **campos)
    session.commit()
    return medio


@router.get("/medios-pago", response_model=list[schemas.MedioPagoOut])
def listar_medios_pago(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return catalogo.listar_medios_pago(session, tenant.filtro_empresa(empresa_id))


# --- Precios (server-side, RN-PRC-003) --------------------------------------
@router.post("/listas-precio", response_model=schemas.ListaPrecioOut, status_code=201)
def crear_lista_precio(
    body: schemas.ListaPrecioCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    if body.sucursal_id is not None:
        tenant.exigir_sucursal(body.sucursal_id)
    lista = precios.crear_lista(session, **body.model_dump())
    session.commit()
    return lista


@router.get("/listas-precio", response_model=list[schemas.ListaPrecioOut])
def listar_listas_precio(
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return precios.listar_listas(session, marca_id)


@router.post(
    "/listas-precio/{lista_id}/precios",
    response_model=schemas.PrecioOut,
    status_code=201,
)


def fijar_precio(
    lista_id: uuid.UUID,
    body: schemas.PrecioCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Alta de precio en una lista. No hay PATCH: corregir un precio es una
    lista nueva, para que el histórico quede auditable (RN-PRC-005)."""
    precio = precios.fijar_precio(
        session,
        lista_precio_id=lista_id,
        producto_comercial_id=body.producto_comercial_id,
        monto=body.monto,
    )
    session.commit()
    return precio


@router.get("/carta", response_model=list[schemas.CartaItemOut])
def carta(
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Catálogo vendible con el precio ya resuelto — lo que el PDV renderiza
    en vez de traer un precio propio."""
    tenant.exigir_sucursal(sucursal_id)
    return precios.carta(
        session,
        sucursal_id=sucursal_id,
        canal=canal,
        modalidad=modalidad,
        marca_id=marca_id,
    )
