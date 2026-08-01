"""Routers FastAPI del módulo accounting: plan de cuentas, periodos, asientos
y mapeo de asientos automáticos."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.accounting.api import schemas
from src.modules.accounting.application import asientos, caja, cuentas, pagos, periodos, reglas
from src.modules.accounting.infrastructure.repositories import AsientoRepo
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.application.queries_publicas import tiene_permiso
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/accounting", tags=["accounting"])

CUENTA_ADMINISTRAR = "accounting.cuenta_administrar"
PERIODO_ADMINISTRAR = "accounting.periodo_administrar"
ASIENTO_MANUAL = "accounting.asiento_manual"
LEER = "accounting.leer"
PAGO_GESTIONAR = "accounting.pago_gestionar"
PAGO_APROBAR = "accounting.pago_aprobar"
CAJA_OPERAR = "accounting.caja_operar"
ARQUEO_REGISTRAR = "accounting.arqueo_registrar"


# --- Plan de cuentas ----------------------------------------------------------
@router.post("/cuentas-contables", response_model=schemas.CuentaContableOut, status_code=201)
def crear_cuenta(
    body: schemas.CuentaContableCreate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    cuenta = cuentas.crear_cuenta(session, **body.model_dump())
    session.commit()
    return cuenta


@router.get("/cuentas-contables", response_model=list[schemas.CuentaContableOut])
def listar_cuentas(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return cuentas.listar_cuentas(session, empresa_id)


@router.patch("/cuentas-contables/{cuenta_id}", response_model=schemas.CuentaContableOut)
def editar_cuenta(
    cuenta_id: uuid.UUID,
    body: schemas.CuentaContableUpdate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    cuenta = cuentas.editar_cuenta(session, cuenta_id, **body.model_dump())
    session.commit()
    return cuenta


# --- Periodo contable ----------------------------------------------------------
@router.post("/periodos", response_model=schemas.PeriodoContableOut, status_code=201)
def abrir_periodo(
    body: schemas.PeriodoContableCreate,
    _: Usuario = Depends(require_permission(PERIODO_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    periodo = periodos.abrir_periodo(session, **body.model_dump())
    session.commit()
    return periodo


@router.get("/periodos", response_model=list[schemas.PeriodoContableOut])
def listar_periodos(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return periodos.listar_periodos(session, empresa_id)


@router.post("/periodos/{periodo_id}/cerrar", response_model=schemas.PeriodoContableOut)
def cerrar_periodo(
    periodo_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PERIODO_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    periodo = periodos.cerrar_periodo(session, periodo_id, cerrado_por=actor.id)
    session.commit()
    return periodo


# --- Asiento --------------------------------------------------------------------
@router.post("/asientos", response_model=schemas.AsientoOut, status_code=201)
def crear_asiento_manual(
    body: schemas.AsientoManualCreate,
    actor: Usuario = Depends(require_permission(ASIENTO_MANUAL)),
    session: Session = Depends(get_db),
):
    asiento = asientos.crear_asiento_manual(
        session,
        empresa_id=body.empresa_id,
        fecha=body.fecha,
        glosa=body.glosa,
        lineas=[li.model_dump() for li in body.lineas],
        creado_por=actor.id,
    )
    session.commit()
    return asiento


@router.get("/asientos", response_model=list[schemas.AsientoOut])
def listar_asientos(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return AsientoRepo(session).list(empresa_id)


@router.get("/asientos/{asiento_id}", response_model=schemas.AsientoOut)
def ver_asiento(
    asiento_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    asiento = AsientoRepo(session).get(asiento_id)
    if asiento is None:
        raise HTTPException(404, "asiento no encontrado")
    return asiento


@router.get("/asientos/{asiento_id}/lineas", response_model=list[schemas.AsientoLineaOut])
def ver_lineas_asiento(
    asiento_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return AsientoRepo(session).lineas(asiento_id)


@router.post("/asientos/{asiento_id}/anular", response_model=schemas.AsientoOut)
def anular_asiento(
    asiento_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ASIENTO_MANUAL)),
    session: Session = Depends(get_db),
):
    reversa = asientos.anular_asiento(session, asiento_id, actor_id=actor.id)
    session.commit()
    return reversa


# --- Regla de asiento (mapeo evento→cuentas) -----------------------------------
@router.post("/reglas-asiento", response_model=schemas.ReglaAsientoOut, status_code=201)
def crear_regla_asiento(
    body: schemas.ReglaAsientoCreate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    regla = reglas.crear_regla_asiento(session, **body.model_dump())
    session.commit()
    return regla


@router.get("/reglas-asiento", response_model=list[schemas.ReglaAsientoOut])
def listar_reglas_asiento(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return reglas.listar_reglas_asiento(session, empresa_id)


# --- Pago a proveedor (PROC-CTB-003) --------------------------------------------
@router.post("/pagos-proveedor", response_model=schemas.MovimientoDineroOut, status_code=201)
def registrar_pago(
    body: schemas.PagoProveedorCreate,
    actor: Usuario = Depends(require_permission(PAGO_GESTIONAR)),
    session: Session = Depends(get_db),
):
    movimiento = pagos.registrar_pago(session, solicitado_por=actor.id, **body.model_dump())
    session.commit()
    return movimiento


@router.get("/pagos-proveedor", response_model=list[schemas.MovimientoDineroOut])
def listar_pagos(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return pagos.listar_pagos(session, empresa_id)


@router.post(
    "/pagos-proveedor/{movimiento_id}/ejecutar", response_model=schemas.MovimientoDineroOut
)


def ejecutar_pago(
    movimiento_id: uuid.UUID,
    body: schemas.EjecutarPagoIn,
    actor: Usuario = Depends(require_permission(PAGO_GESTIONAR)),
    session: Session = Depends(get_db),
):
    puede_aprobar = tiene_permiso(session, actor.id, PAGO_APROBAR)
    movimiento = pagos.ejecutar_pago(
        session,
        movimiento_id,
        actor_id=actor.id,
        puede_aprobar_monto=puede_aprobar,
        umbral=settings.accounting_umbral_aprobacion_pago,
        medio_pago=body.medio_pago,
        constancia=body.constancia,
    )
    session.commit()
    return movimiento


@router.post(
    "/pagos-proveedor/{movimiento_id}/rechazar", response_model=schemas.MovimientoDineroOut
)


def rechazar_pago(
    movimiento_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PAGO_GESTIONAR)),
    session: Session = Depends(get_db),
):
    movimiento = pagos.rechazar_pago(session, movimiento_id, actor_id=actor.id)
    session.commit()
    return movimiento


# --- Caja (PROC-CTB-001/002) — slice mínimo, ver módulo application/caja.py -----
@router.post("/cajas/apertura", response_model=schemas.AperturaCajaOut, status_code=201)
def abrir_caja(
    body: schemas.AbrirCajaIn,
    actor: Usuario = Depends(require_permission(CAJA_OPERAR)),
    session: Session = Depends(get_db),
):
    apertura = caja.abrir_caja(session, cajero_id=actor.id, **body.model_dump())
    session.commit()
    return apertura


@router.post(
    "/cajas/apertura/{apertura_caja_id}/cierre", response_model=schemas.CierreCajaOut
)


def cerrar_caja(
    apertura_caja_id: uuid.UUID,
    body: schemas.CerrarCajaIn,
    actor: Usuario = Depends(require_permission(CAJA_OPERAR)),
    session: Session = Depends(get_db),
):
    cierre = caja.cerrar_caja(
        session, apertura_caja_id, cajero_id=actor.id, **body.model_dump()
    )
    session.commit()
    return cierre


@router.get("/cajas/abiertas", response_model=list[schemas.CajaAbiertaOut])
def listar_cajas_abiertas(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return caja.cajas_abiertas(session, empresa_id)


@router.post("/arqueos", response_model=schemas.ArqueoOut, status_code=201)
def registrar_arqueo(
    body: schemas.ArqueoIn,
    actor: Usuario = Depends(require_permission(ARQUEO_REGISTRAR)),
    session: Session = Depends(get_db),
):
    arqueo = caja.registrar_arqueo(session, realizado_por=actor.id, **body.model_dump())
    session.commit()
    return arqueo
