"""Agenda unificada: mantenimientos próximos/vencidos + documentos por
vencer/vencidos, en una sola lista ordenada por fecha. Es la pregunta con la
que se abre el módulo: "¿qué se me viene?", no "deme la tabla de planes"."""

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.modules.assets.application import planes as planes_uc
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    DocumentoVigenciaRepo,
    PlanMantenimientoRepo,
    VehiculoRepo,
)
from src.shared import fechas


def _item_de_plan(
    session: Session, plan, *, hoy: date, limite: date, sucursal_id: uuid.UUID | None
) -> dict | None:
    activo = ActivoRepo(session).get(plan.activo_id)
    if activo is None:
        return None
    if sucursal_id is not None and activo.sucursal_id != sucursal_id:
        return None
    km_actual = None
    if activo.tipo == "vehiculo":
        vehiculo = VehiculoRepo(session).get(activo.id)
        km_actual = vehiculo.kilometraje_actual if vehiculo else None
    estado = planes_uc.estado_de(plan, activo, km_actual, hoy=hoy)
    if estado.estado == "al_dia" and (
        estado.proxima_fecha is None or estado.proxima_fecha > limite
    ):
        return None
    return {
        "tipo": "mantenimiento",
        "estado": estado.estado,
        "fecha": estado.proxima_fecha,
        "km": estado.proximo_km,
        "activo_id": activo.id,
        "plan_id": plan.id,
        "nombre": f"{activo.nombre} — {plan.nombre}",
    }


def _item_de_documento(
    session: Session, documento, *, hoy: date, limite: date, sucursal_id: uuid.UUID | None
) -> dict | None:
    if sucursal_id is not None:
        if documento.sujeto_tipo != "activo":
            return None
        activo = ActivoRepo(session).get(documento.sujeto_id)
        if activo is None or activo.sucursal_id != sucursal_id:
            return None
    estado = rules.estado_documento(
        hoy=hoy,
        fecha_vencimiento=documento.fecha_vencimiento,
        dias_aviso=documento.dias_aviso,
        renovado=False,
    )
    if estado.estado == "vigente" and documento.fecha_vencimiento > limite:
        return None
    return {
        "tipo": "documento",
        "estado": "al_dia" if estado.estado == "vigente" else estado.estado,
        "fecha": documento.fecha_vencimiento,
        "km": None,
        "documento_id": documento.id,
        "sujeto_tipo": documento.sujeto_tipo,
        "sujeto_id": documento.sujeto_id,
        "nombre": documento.tipo_documento,
    }


def agenda(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    dias: int = 90,
    sucursal_id: uuid.UUID | None = None,
) -> list[dict]:
    hoy = fechas.hoy()
    limite = hoy + timedelta(days=dias)

    items = [
        item
        for plan in PlanMantenimientoRepo(session).list_activos(empresa_id)
        if (item := _item_de_plan(session, plan, hoy=hoy, limite=limite, sucursal_id=sucursal_id))
        is not None
    ]
    items += [
        item
        for documento in DocumentoVigenciaRepo(session).list_vigentes(empresa_id)
        if (
            item := _item_de_documento(
                session, documento, hoy=hoy, limite=limite, sucursal_id=sucursal_id
            )
        )
        is not None
    ]

    items.sort(key=lambda i: (i["fecha"] is None, i["fecha"]))
    return items
