"""Routers FastAPI del módulo sales: venta, cobro y catálogo comercial."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.modules.sales.api import schemas
from src.modules.sales.application import (
    catalogo,
    comprobantes,
    queries_publicas,
    tasks,
    ventas,
)
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
    SalesError,
)
from src.modules.sales.infrastructure.repositories import ComprobanteRepo
from src.modules.users.api.deps import get_db, require_permission
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

_HTTP_STATUS: dict[type[SalesError], int] = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ReglaNegocio: status.HTTP_409_CONFLICT,
}


def _http(err: SalesError) -> HTTPException:
    return HTTPException(_HTTP_STATUS.get(type(err), 400), str(err))


# --- Venta ------------------------------------------------------------------
@router.post("/ventas", response_model=schemas.VentaOut, status_code=201)
def crear_venta(
    body: schemas.VentaCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    session: Session = Depends(get_db),
):
    try:
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
        )
    except (NoEncontrado, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return venta


@router.get("/ventas/{venta_id}", response_model=schemas.VentaOut)
def ver_venta(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    from src.modules.sales.infrastructure.repositories import VentaRepo

    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise HTTPException(404, "venta no encontrada")
    return venta


@router.post("/ventas/{venta_id}/pagos", response_model=schemas.PagoOut, status_code=201)
def registrar_pago(
    venta_id: uuid.UUID,
    body: schemas.PagoCreate,
    _: Usuario = Depends(require_permission(COBRAR)),
    session: Session = Depends(get_db),
):
    try:
        pago, _venta, comprobante = ventas.registrar_pago(
            session,
            venta_id=venta_id,
            medio_pago_id=body.medio_pago_id,
            monto=body.monto,
            idempotency_key=body.idempotency_key,
            referencia_externa=body.referencia_externa,
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    session: Session = Depends(get_db),
):
    try:
        venta = ventas.anular_venta(session, venta_id, actor.id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return venta


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
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    except FactilizaError as e:
        session.commit()  # conserva el intento contado
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
    try:
        prod = catalogo.crear_producto(session, **body.model_dump())
    except Conflicto as e:
        raise _http(e) from e
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
    try:
        prod = catalogo.editar_producto(session, producto_id, **body.model_dump())
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return prod


@router.post("/medios-pago", response_model=schemas.MedioPagoOut, status_code=201)
def crear_medio_pago(
    body: schemas.MedioPagoCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    medio = catalogo.crear_medio_pago(session, **body.model_dump())
    session.commit()
    return medio


@router.get("/medios-pago", response_model=list[schemas.MedioPagoOut])
def listar_medios_pago(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return catalogo.listar_medios_pago(session, empresa_id)
