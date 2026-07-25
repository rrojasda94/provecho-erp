"""Routers FastAPI del módulo accounting: plan de cuentas, periodos, asientos
y mapeo de asientos automáticos."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.modules.accounting.api import schemas
from src.modules.accounting.application import asientos, cuentas, periodos, reglas
from src.modules.accounting.application.errors import (
    AccountingError,
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.accounting.infrastructure.repositories import AsientoRepo
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/accounting", tags=["accounting"])

CUENTA_ADMINISTRAR = "accounting.cuenta_administrar"
PERIODO_ADMINISTRAR = "accounting.periodo_administrar"
ASIENTO_MANUAL = "accounting.asiento_manual"
LEER = "accounting.leer"

_HTTP_STATUS: dict[type[AccountingError], int] = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ReglaNegocio: status.HTTP_409_CONFLICT,
}


def _http(err: AccountingError) -> HTTPException:
    return HTTPException(_HTTP_STATUS.get(type(err), 400), str(err))


# --- Plan de cuentas ----------------------------------------------------------
@router.post("/cuentas-contables", response_model=schemas.CuentaContableOut, status_code=201)
def crear_cuenta(
    body: schemas.CuentaContableCreate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    try:
        cuenta = cuentas.crear_cuenta(session, **body.model_dump())
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    try:
        cuenta = cuentas.editar_cuenta(session, cuenta_id, **body.model_dump())
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return cuenta


# --- Periodo contable ----------------------------------------------------------
@router.post("/periodos", response_model=schemas.PeriodoContableOut, status_code=201)
def abrir_periodo(
    body: schemas.PeriodoContableCreate,
    _: Usuario = Depends(require_permission(PERIODO_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    try:
        periodo = periodos.abrir_periodo(session, **body.model_dump())
    except ReglaNegocio as e:
        raise _http(e) from e
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
    try:
        periodo = periodos.cerrar_periodo(session, periodo_id, cerrado_por=actor.id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return periodo


# --- Asiento --------------------------------------------------------------------
@router.post("/asientos", response_model=schemas.AsientoOut, status_code=201)
def crear_asiento_manual(
    body: schemas.AsientoManualCreate,
    actor: Usuario = Depends(require_permission(ASIENTO_MANUAL)),
    session: Session = Depends(get_db),
):
    try:
        asiento = asientos.crear_asiento_manual(
            session,
            empresa_id=body.empresa_id,
            fecha=body.fecha,
            glosa=body.glosa,
            lineas=[li.model_dump() for li in body.lineas],
            creado_por=actor.id,
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    try:
        reversa = asientos.anular_asiento(session, asiento_id, actor_id=actor.id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return reversa


# --- Regla de asiento (mapeo evento→cuentas) -----------------------------------
@router.post("/reglas-asiento", response_model=schemas.ReglaAsientoOut, status_code=201)
def crear_regla_asiento(
    body: schemas.ReglaAsientoCreate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    session: Session = Depends(get_db),
):
    try:
        regla = reglas.crear_regla_asiento(session, **body.model_dump())
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return regla


@router.get("/reglas-asiento", response_model=list[schemas.ReglaAsientoOut])
def listar_reglas_asiento(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return reglas.listar_reglas_asiento(session, empresa_id)
