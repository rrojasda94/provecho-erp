"""Casos de uso de campaña: crear (brief) → aprobar → lanzar (en_curso) →
cerrar. Incluye la verificación en sitio del material en cada sucursal
(RN-MKT-005), que es un hecho de la campaña, no una entidad aparte.

Sin brief completo la campaña no se aprueba, y sin aprobación no sale a
canal (RN-MKT-003).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.marketing.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.marketing.domain import rules
from src.modules.marketing.infrastructure.models import (
    Campana,
    ImplementacionMaterialSucursal,
)
from src.modules.marketing.infrastructure.repositories import CampanaRepo
from src.modules.users.infrastructure.models import Marca


def crear_campana(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    marca_id: uuid.UUID,
    nombre: str,
    tipo: str,
    canal: str,
    creado_por: uuid.UUID,
    idempotency_key: str,
    objetivo: str | None = None,
    publico_objetivo: str | None = None,
    presupuesto: Decimal | None = None,
    kpi: str | None = None,
) -> Campana:
    repo = CampanaRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    if session.get(Marca, marca_id) is None:
        raise NoEncontrado(f"marca {marca_id} no encontrada")

    return repo.add(
        Campana(
            empresa_id=empresa_id,
            marca_id=marca_id,
            nombre=nombre,
            tipo=tipo,
            canal=canal,
            objetivo=objetivo,
            publico_objetivo=publico_objetivo,
            presupuesto=Decimal(str(presupuesto)) if presupuesto is not None else None,
            kpi=kpi,
            estado="brief",
            creado_por=creado_por,
            idempotency_key=idempotency_key,
        )
    )


def completar_brief(
    session: Session,
    campana_id: uuid.UUID,
    *,
    objetivo: str | None = None,
    publico_objetivo: str | None = None,
    presupuesto: Decimal | None = None,
    kpi: str | None = None,
) -> Campana:
    campana = _campana(session, campana_id)
    if campana.estado != "brief":
        raise Conflicto(f"la campaña está {campana.estado}; el brief ya no se edita")
    if objetivo is not None:
        campana.objetivo = objetivo
    if publico_objetivo is not None:
        campana.publico_objetivo = publico_objetivo
    if presupuesto is not None:
        campana.presupuesto = Decimal(str(presupuesto))
    if kpi is not None:
        campana.kpi = kpi
    session.flush()
    return campana


def aprobar_campana(
    session: Session, campana_id: uuid.UUID, *, aprobada_por: uuid.UUID
) -> Campana:
    campana = _campana(session, campana_id)
    if not rules.puede_aprobar(campana.estado):
        raise Conflicto(f"la campaña está {campana.estado}; no admite aprobación")
    faltantes = rules.brief_incompleto(campana)
    if faltantes:
        raise ReglaNegocio(
            f"brief incompleto, faltan: {', '.join(faltantes)} (RN-MKT-003)"
        )
    campana.estado = "aprobada"
    campana.aprobada_por = aprobada_por
    session.flush()
    return campana


def lanzar_campana(session: Session, campana_id: uuid.UUID) -> Campana:
    campana = _campana(session, campana_id)
    if not rules.puede_lanzar(campana.estado):
        raise Conflicto(
            f"la campaña está {campana.estado}; sin brief aprobado no sale a canal"
        )
    campana.estado = "en_curso"
    session.flush()
    event_bus.publish(
        "marketing.campana_lanzada",
        {
            "campana_id": str(campana.id),
            "marca_id": str(campana.marca_id),
            "tipo": campana.tipo,
            "presupuesto": str(campana.presupuesto),
        },
    )
    return campana


def cerrar_campana(session: Session, campana_id: uuid.UUID) -> Campana:
    campana = _campana(session, campana_id)
    if not rules.puede_cerrar(campana.estado):
        raise Conflicto(f"la campaña está {campana.estado}; no admite cierre")
    campana.estado = "cerrada"
    session.flush()
    return campana


def registrar_implementacion_material(
    session: Session,
    campana_id: uuid.UUID,
    *,
    sucursal_id: uuid.UUID,
    verificado_por: uuid.UUID,
    completa: bool,
    incidencia: str | None = None,
    fecha: date | None = None,
) -> ImplementacionMaterialSucursal:
    """Verificación en sitio (RN-MKT-005). Repetir la verificación del mismo
    día para la misma sucursal actualiza la fila, no crea otra."""
    campana = _campana(session, campana_id)
    if campana.estado == "brief":
        raise Conflicto("la campaña sigue en brief; no hay material que verificar")
    if not completa and not incidencia:
        raise ReglaNegocio("una implementación incompleta requiere incidencia")

    fecha = fecha or date.today()
    registro = session.scalar(
        select(ImplementacionMaterialSucursal).where(
            ImplementacionMaterialSucursal.campana_id == campana_id,
            ImplementacionMaterialSucursal.sucursal_id == sucursal_id,
            ImplementacionMaterialSucursal.fecha == fecha,
        )
    )
    if registro is not None:
        registro.verificado_por = verificado_por
        registro.completa = completa
        registro.incidencia = incidencia
        session.flush()
        return registro

    registro = ImplementacionMaterialSucursal(
        campana_id=campana_id,
        sucursal_id=sucursal_id,
        fecha=fecha,
        verificado_por=verificado_por,
        completa=completa,
        incidencia=incidencia,
    )
    session.add(registro)
    session.flush()
    return registro


def _campana(session: Session, campana_id: uuid.UUID) -> Campana:
    campana = CampanaRepo(session).get(campana_id)
    if campana is None or campana.deleted_at is not None:
        raise NoEncontrado("campaña no encontrada")
    return campana
