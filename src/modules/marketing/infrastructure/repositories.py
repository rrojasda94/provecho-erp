"""Repositorios SQLAlchemy del módulo marketing. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.marketing.infrastructure.models import (
    Campana,
    EncuestaSatisfaccion,
    Lead,
    PiezaContenido,
)


class CampanaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, campana_id: uuid.UUID) -> Campana | None:
        return self.s.get(Campana, campana_id)

    def get_by_idempotency(self, idempotency_key: str) -> Campana | None:
        return self.s.scalar(
            select(Campana).where(Campana.idempotency_key == idempotency_key)
        )

    def listar(
        self, empresa_id: uuid.UUID | None, *, estado: str | None = None
    ) -> list[Campana]:
        stmt = select(Campana).where(Campana.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(Campana.empresa_id == empresa_id)
        if estado is not None:
            stmt = stmt.where(Campana.estado == estado)
        return list(self.s.scalars(stmt.order_by(Campana.created_at.desc())))

    def add(self, campana: Campana) -> Campana:
        self.s.add(campana)
        self.s.flush()
        return campana


class LeadRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, lead_id: uuid.UUID) -> Lead | None:
        return self.s.get(Lead, lead_id)

    def get_by_idempotency(self, idempotency_key: str) -> Lead | None:
        return self.s.scalar(select(Lead).where(Lead.idempotency_key == idempotency_key))

    def sin_atribuir_de_cliente(self, cliente_id: uuid.UUID) -> list[Lead]:
        """Leads de ese cliente que todavía no apuntan a una venta, solo de
        campañas en curso — una campaña cerrada ya no se lleva el crédito."""
        return list(
            self.s.scalars(
                select(Lead)
                .join(Campana, Campana.id == Lead.campana_id)
                .where(
                    Lead.cliente_id == cliente_id,
                    Lead.venta_id.is_(None),
                    Campana.estado == "en_curso",
                )
            )
        )

    def de_campana(self, campana_id: uuid.UUID) -> list[Lead]:
        return list(self.s.scalars(select(Lead).where(Lead.campana_id == campana_id)))

    def add(self, lead: Lead) -> Lead:
        self.s.add(lead)
        self.s.flush()
        return lead


class PiezaContenidoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, pieza_id: uuid.UUID) -> PiezaContenido | None:
        return self.s.get(PiezaContenido, pieza_id)

    def add(self, pieza: PiezaContenido) -> PiezaContenido:
        self.s.add(pieza)
        self.s.flush()
        return pieza


class EncuestaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, encuesta_id: uuid.UUID) -> EncuestaSatisfaccion | None:
        return self.s.get(EncuestaSatisfaccion, encuesta_id)

    def de_venta(self, venta_id: uuid.UUID) -> EncuestaSatisfaccion | None:
        return self.s.scalar(
            select(EncuestaSatisfaccion).where(EncuestaSatisfaccion.venta_id == venta_id)
        )

    def add(self, encuesta: EncuestaSatisfaccion) -> EncuestaSatisfaccion:
        self.s.add(encuesta)
        self.s.flush()
        return encuesta
