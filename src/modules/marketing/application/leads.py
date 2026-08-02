"""Casos de uso de lead: registrar la pista que genera la campaña y
atribuirla a la venta real cuando Comercial cierra (RN-MKT-003).

La campaña se mide por leads con `venta_id`, no por volumen bruto: sin la
atribución, el registro de leads no dice nada.
"""

import uuid

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.marketing.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.marketing.domain import rules
from src.modules.marketing.infrastructure.models import Lead
from src.modules.marketing.infrastructure.repositories import CampanaRepo, LeadRepo


def registrar_lead(
    session: Session,
    *,
    campana_id: uuid.UUID,
    canal: str,
    tipo: str,
    idempotency_key: str,
    contacto: str | None = None,
    cliente_id: uuid.UUID | None = None,
) -> Lead:
    repo = LeadRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    campana = CampanaRepo(session).get(campana_id)
    if campana is None or campana.deleted_at is not None:
        raise NoEncontrado("campaña no encontrada")
    if not rules.campana_admite_leads(campana.estado):
        raise Conflicto(
            f"la campaña está {campana.estado}; solo una campaña en curso genera leads"
        )

    lead = repo.add(
        Lead(
            campana_id=campana_id,
            canal=canal,
            tipo=tipo,
            contacto=contacto,
            cliente_id=cliente_id,
            idempotency_key=idempotency_key,
        )
    )
    event_bus.publish(
        "marketing.lead_generado",
        {
            "lead_id": str(lead.id),
            "campana_id": str(campana_id),
            "canal": canal,
            "cliente_id": str(cliente_id) if cliente_id else None,
        },
    )
    return lead


def atribuir_venta(session: Session, lead_id: uuid.UUID, *, venta_id: uuid.UUID) -> Lead:
    """Atribución manual: la hace Marketing cuando reconoce la venta que
    cerró un lead. La automática vive en `listeners.on_venta_confirmada` y
    solo actúa cuando no hay ambigüedad."""
    lead = LeadRepo(session).get(lead_id)
    if lead is None:
        raise NoEncontrado("lead no encontrado")
    if lead.venta_id is not None:
        raise ReglaNegocio("el lead ya está atribuido a una venta")
    lead.venta_id = venta_id
    session.flush()
    return lead
