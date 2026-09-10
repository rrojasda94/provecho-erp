"""Validación de alcance de tenant sobre recursos de assets (ADR-004).

`activo` lleva `empresa_id` propio; el resto del módulo cuelga de un activo
y hereda su alcance. `documento_vigencia` también lleva `empresa_id` propio
porque su sujeto puede no ser un activo (sucursal, empresa o trabajador).
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.assets.application.errors import NoEncontrado
from src.modules.assets.infrastructure.models import (
    Activo,
    CargaCombustible,
    DocumentoVigencia,
    OrdenMantenimiento,
    PlanMantenimiento,
    Vehiculo,
)
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    CargaCombustibleRepo,
    DocumentoVigenciaRepo,
    OrdenMantenimientoRepo,
    PlanMantenimientoRepo,
    VehiculoRepo,
)
from src.modules.rrhh.application.queries_publicas import trabajador_resumen
from src.modules.users.infrastructure.models import Empresa, Sucursal
from src.shared.models import Comprobante


def exigir_activo(session: Session, activo_id: uuid.UUID, tenant: Tenant) -> Activo:
    activo = ActivoRepo(session).get(activo_id)
    if activo is None:
        raise NoEncontrado("activo no encontrado")
    tenant.exigir_empresa(activo.empresa_id)
    return activo


def exigir_vehiculo(session: Session, activo_id: uuid.UUID, tenant: Tenant) -> Vehiculo:
    """El activo ya validado como propio del tenant; acá solo se confirma que
    es un vehículo y no un equipamiento."""
    exigir_activo(session, activo_id, tenant)
    vehiculo = VehiculoRepo(session).get(activo_id)
    if vehiculo is None:
        raise NoEncontrado("el activo no es un vehículo")
    return vehiculo


def exigir_plan(session: Session, plan_id: uuid.UUID, tenant: Tenant) -> PlanMantenimiento:
    plan = PlanMantenimientoRepo(session).get(plan_id)
    if plan is None:
        raise NoEncontrado("plan de mantenimiento no encontrado")
    exigir_activo(session, plan.activo_id, tenant)
    return plan


def exigir_orden_mantenimiento(
    session: Session, orden_id: uuid.UUID, tenant: Tenant
) -> OrdenMantenimiento:
    orden = OrdenMantenimientoRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de mantenimiento no encontrada")
    exigir_activo(session, orden.activo_id, tenant)
    return orden


def exigir_documento(
    session: Session, documento_id: uuid.UUID, tenant: Tenant
) -> DocumentoVigencia:
    documento = DocumentoVigenciaRepo(session).get(documento_id)
    if documento is None:
        raise NoEncontrado("documento no encontrado")
    tenant.exigir_empresa(documento.empresa_id)
    return documento


def exigir_carga_combustible(
    session: Session, carga_id: uuid.UUID, tenant: Tenant
) -> CargaCombustible:
    carga = CargaCombustibleRepo(session).get(carga_id)
    if carga is None:
        raise NoEncontrado("carga de combustible no encontrada")
    exigir_vehiculo(session, carga.vehiculo_id, tenant)
    return carga


def exigir_comprobante_recibido(
    session: Session, comprobante_id: uuid.UUID, tenant: Tenant
) -> Comprobante:
    """El comprobante existe, es de la empresa del tenant y es un documento
    **recibido** (RN-VEH-006 exige que la carga se sustente con un papel que
    la empresa recibió de un proveedor, no uno que ella misma emitió)."""
    comprobante = session.get(Comprobante, comprobante_id)
    if comprobante is None:
        raise NoEncontrado("comprobante no encontrado")
    tenant.exigir_empresa(comprobante.empresa_id)
    if comprobante.direccion != "recibido":
        raise NoEncontrado("comprobante no encontrado")
    return comprobante


def exigir_sujeto(
    session: Session, sujeto_tipo: str, sujeto_id: uuid.UUID, tenant: Tenant
) -> uuid.UUID:
    """Valida que el sujeto de un `documento_vigencia` exista y sea del
    tenant, y devuelve su `empresa_id`.

    Cada tipo se resuelve contra su propio dueño: `activo` por este módulo,
    `sucursal`/`empresa` por `users` (excepción `*` de
    `tests/test_arquitectura.py`), `trabajador` por el contrato público de
    `rrhh` — nunca su ORM.
    """
    if sujeto_tipo == "activo":
        return exigir_activo(session, sujeto_id, tenant).empresa_id
    if sujeto_tipo == "sucursal":
        sucursal = session.get(Sucursal, sujeto_id)
        if sucursal is None:
            raise NoEncontrado("sucursal no encontrada")
        tenant.exigir_empresa(sucursal.empresa_id)
        return sucursal.empresa_id
    if sujeto_tipo == "empresa":
        empresa = session.get(Empresa, sujeto_id)
        if empresa is None:
            raise NoEncontrado("empresa no encontrada")
        tenant.exigir_empresa(empresa.id)
        return empresa.id
    # sujeto_tipo == "trabajador"
    resumen = trabajador_resumen(session, sujeto_id)
    if resumen is None:
        raise NoEncontrado("trabajador no encontrado")
    tenant.exigir_empresa(resumen["empresa_id"])
    return resumen["empresa_id"]
