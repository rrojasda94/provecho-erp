"""Plan de mantenimiento de un activo: su frecuencia recomendada (RN-MNT-001)
y el aviso con anticipación configurable (RN-MNT-005)."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from src.modules.assets.application.errors import NoEncontrado, ReglaNegocio
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.models import Activo, PlanMantenimiento
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    PlanMantenimientoRepo,
    VehiculoRepo,
)
from src.shared import fechas


def crear_plan(
    session: Session,
    *,
    activo_id: uuid.UUID,
    nombre: str,
    descripcion: str | None = None,
    cada_dias: int | None = None,
    cada_km: int | None = None,
    dias_aviso: int = rules.DIAS_AVISO_MANTENIMIENTO_DEFECTO,
    km_aviso: int = rules.KM_AVISO_MANTENIMIENTO_DEFECTO,
    proveedor_servicio_id: uuid.UUID | None = None,
) -> PlanMantenimiento:
    if cada_dias is None and cada_km is None:
        raise ReglaNegocio("un plan necesita al menos cada_dias o cada_km")
    activo = ActivoRepo(session).get(activo_id)
    if activo is None:
        raise NoEncontrado("activo no encontrado")
    if cada_km is not None and activo.tipo != "vehiculo":
        raise ReglaNegocio("cada_km solo aplica a un activo tipo vehiculo")

    km_base = None
    if activo.tipo == "vehiculo":
        vehiculo = VehiculoRepo(session).get(activo_id)
        km_base = vehiculo.kilometraje_actual if vehiculo else None

    return PlanMantenimientoRepo(session).add(
        PlanMantenimiento(
            activo_id=activo_id,
            nombre=nombre,
            descripcion=descripcion,
            cada_dias=cada_dias,
            cada_km=cada_km,
            dias_aviso=dias_aviso,
            km_aviso=km_aviso,
            proveedor_servicio_id=proveedor_servicio_id,
            km_base=km_base,
        )
    )


def editar_plan(
    session: Session,
    plan_id: uuid.UUID,
    *,
    nombre: str | None = None,
    descripcion: str | None = None,
    cada_dias: int | None = None,
    cada_km: int | None = None,
    dias_aviso: int | None = None,
    km_aviso: int | None = None,
    activo: bool | None = None,
) -> PlanMantenimiento:
    plan = PlanMantenimientoRepo(session).get(plan_id)
    if plan is None:
        raise NoEncontrado("plan de mantenimiento no encontrado")
    for campo, valor in (
        ("nombre", nombre),
        ("descripcion", descripcion),
        ("cada_dias", cada_dias),
        ("cada_km", cada_km),
        ("dias_aviso", dias_aviso),
        ("km_aviso", km_aviso),
        ("activo", activo),
    ):
        if valor is not None:
            setattr(plan, campo, valor)
    return plan


def estado_de(
    plan: PlanMantenimiento, activo: Activo, km_actual: int | None, *, hoy: date | None = None
) -> rules.EstadoPlan:
    return rules.estado_plan(
        hoy=hoy or fechas.hoy(),
        cada_dias=plan.cada_dias,
        cada_km=plan.cada_km,
        dias_aviso=plan.dias_aviso,
        km_aviso=plan.km_aviso,
        ultima_fecha=plan.ultima_fecha,
        fecha_base=fechas.a_fecha_local(plan.created_at) or fechas.hoy(),
        ultimo_km=plan.ultimo_km,
        km_base=plan.km_base,
        km_actual=km_actual,
    )


def q_planes(session: Session, empresa_id: uuid.UUID | None):
    return PlanMantenimientoRepo(session).q_activos(empresa_id)


def q_de_activo(session: Session, activo_id: uuid.UUID):
    return PlanMantenimientoRepo(session).q_de_activo(activo_id)
