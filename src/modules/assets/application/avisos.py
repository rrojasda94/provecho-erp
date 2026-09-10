"""Barrido diario de vencimientos: mantenimiento próximo/vencido y
documentos por vencer/vencidos (RN-MNT-005).

Publica cada aviso **una sola vez** por ventana: `aviso_proximo_en`/
`aviso_vencido_en` en la fila son la marca de que ya se avisó, para que
correr el barrido de nuevo el mismo día (o el siguiente, mientras nada
cambie) no duplique la campana. Se limpian cuando el estado vuelve a la
normalidad — al realizar la orden (`ordenes.realizar_orden`) o al editar el
plan/documento — para que un vencimiento futuro sí vuelva a avisar.
"""

from datetime import date

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.assets.application import planes as planes_uc
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    DocumentoVigenciaRepo,
    PlanMantenimientoRepo,
    VehiculoRepo,
)
from src.shared import fechas


def _revisar_plan(session: Session, plan, hoy: date) -> str | None:
    """Publica el aviso del plan si corresponde y devuelve qué se publicó
    (`None` si no había nada nuevo)."""
    activo = ActivoRepo(session).get(plan.activo_id)
    if activo is None:
        return None
    km_actual = None
    if activo.tipo == "vehiculo":
        vehiculo = VehiculoRepo(session).get(activo.id)
        km_actual = vehiculo.kilometraje_actual if vehiculo else None

    estado = planes_uc.estado_de(plan, activo, km_actual, hoy=hoy)
    if estado.estado == "al_dia":
        plan.aviso_proximo_en = None
        plan.aviso_vencido_en = None
        return None

    payload = {
        "plan_id": str(plan.id),
        "activo_id": str(activo.id),
        "empresa_id": str(activo.empresa_id),
        "sucursal_id": str(activo.sucursal_id) if activo.sucursal_id else None,
        "nombre": activo.nombre,
        "plan_nombre": plan.nombre,
        "proxima_fecha": str(estado.proxima_fecha) if estado.proxima_fecha else None,
        "proximo_km": estado.proximo_km,
    }
    if estado.estado == "vencido" and plan.aviso_vencido_en is None:
        event_bus.publish("assets.mantenimiento_vencido", payload, session=session)
        plan.aviso_vencido_en = hoy
        return "mantenimiento_vencido"
    if estado.estado == "proximo" and plan.aviso_proximo_en is None:
        event_bus.publish("assets.mantenimiento_proximo", payload, session=session)
        plan.aviso_proximo_en = hoy
        return "mantenimiento_proximo"
    return None


def _revisar_documento(session: Session, documento, hoy: date) -> str | None:
    estado = rules.estado_documento(
        hoy=hoy,
        fecha_vencimiento=documento.fecha_vencimiento,
        dias_aviso=documento.dias_aviso,
        renovado=False,
    )
    if estado.estado == "vigente":
        documento.aviso_proximo_en = None
        documento.aviso_vencido_en = None
        return None

    payload = {
        "documento_id": str(documento.id),
        "empresa_id": str(documento.empresa_id),
        "sujeto_tipo": documento.sujeto_tipo,
        "sujeto_id": str(documento.sujeto_id),
        "tipo_documento": documento.tipo_documento,
        "fecha_vencimiento": str(documento.fecha_vencimiento),
    }
    if estado.estado == "vencido" and documento.aviso_vencido_en is None:
        event_bus.publish("assets.documento_vencido", payload, session=session)
        documento.aviso_vencido_en = hoy
        return "documento_vencido"
    if estado.estado == "proximo" and documento.aviso_proximo_en is None:
        event_bus.publish("assets.documento_por_vencer", payload, session=session)
        documento.aviso_proximo_en = hoy
        return "documento_por_vencer"
    return None


def barrer(session: Session, *, hoy: date | None = None) -> dict:
    """Sin filtro de empresa: un barrido periódico no tiene tenant, y un plan
    o un documento vencido lo está para toda empresa (mismo criterio que
    `inventory.bloquear_lotes_vencidos`)."""
    hoy = hoy or fechas.hoy()
    publicados = {
        "mantenimiento_proximo": 0,
        "mantenimiento_vencido": 0,
        "documento_por_vencer": 0,
        "documento_vencido": 0,
    }

    for plan in PlanMantenimientoRepo(session).list_activos():
        clave = _revisar_plan(session, plan, hoy)
        if clave is not None:
            publicados[clave] += 1

    for documento in DocumentoVigenciaRepo(session).list_vigentes():
        clave = _revisar_documento(session, documento, hoy)
        if clave is not None:
            publicados[clave] += 1

    return publicados
