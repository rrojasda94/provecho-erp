"""Repositorios SQLAlchemy del módulo marketing. La sesión es la Unit of Work."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.marketing.infrastructure.models import (
    Campana,
    CampanaMetrica,
    EncuestaPlantilla,
    EncuestaPregunta,
    EncuestaRespuesta,
    EncuestaSatisfaccion,
    EvaluacionAgencia,
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

    def q_listar(
        self, empresa_id: uuid.UUID | None, *, estado: str | None = None
    ):
        """La consulta, sin ejecutar: el router la pagina (ADR-026)."""
        stmt = select(Campana).where(Campana.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(Campana.empresa_id == empresa_id)
        if estado is not None:
            stmt = stmt.where(Campana.estado == estado)
        return stmt.order_by(Campana.created_at.desc())

    def listar(
        self, empresa_id: uuid.UUID | None, *, estado: str | None = None
    ) -> list[Campana]:
        return list(self.s.scalars(self.q_listar(empresa_id, estado=estado)))

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

    def q_de_campana(self, campana_id: uuid.UUID):
        return (
            select(Lead)
            .where(Lead.campana_id == campana_id)
            .order_by(Lead.created_at.desc())
        )

    def campana_de_venta(self, venta_id: uuid.UUID) -> uuid.UUID | None:
        """Campaña que se llevó el crédito de esa venta, vía el lead
        atribuido. Es lo que permite acreditarle a la campaña la satisfacción
        del cliente que ella trajo."""
        return self.s.scalar(select(Lead.campana_id).where(Lead.venta_id == venta_id))

    def de_campana(self, campana_id: uuid.UUID) -> list[Lead]:
        return list(self.s.scalars(self.q_de_campana(campana_id)))

    def add(self, lead: Lead) -> Lead:
        self.s.add(lead)
        self.s.flush()
        return lead


class PiezaContenidoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def q_listar(
        self,
        campana_ids: list[uuid.UUID] | None = None,
        estado: str | None = None,
        desde=None,
        hasta=None,
    ):
        """La consulta sin ejecutar: el router la pagina (ADR-026).

        `pieza_contenido` no lleva empresa —cuelga de la marca, y la marca es
        del grupo, no de una empresa— así que el alcance se acota por las
        campañas del tenant. La pieza **sin campaña** (contenido de marca
        siempre-verde) queda visible para cualquiera con `marketing.leer`,
        igual que hoy al pedirla por id (`scope.exigir_pieza` no la
        restringe). Es una excepción de tenant declarada, no un descuido.
        """
        q = select(PiezaContenido)
        if campana_ids is not None:
            q = q.where(
                PiezaContenido.campana_id.in_(campana_ids)
                | PiezaContenido.campana_id.is_(None)
            )
        if estado is not None:
            q = q.where(PiezaContenido.estado == estado)
        if desde is not None:
            q = q.where(PiezaContenido.fecha_publicacion >= desde)
        if hasta is not None:
            q = q.where(PiezaContenido.fecha_publicacion <= hasta)
        return q.order_by(PiezaContenido.fecha_publicacion.desc())

    def del_rango(
        self, campana_ids: list[uuid.UUID], desde, hasta
    ) -> list[PiezaContenido]:
        """El calendario: ascendente por fecha, porque una semana se lee del
        lunes al domingo y no al revés."""
        return list(
            self.s.scalars(
                self.q_listar(campana_ids, desde=desde, hasta=hasta).order_by(
                    None
                ).order_by(
                    PiezaContenido.fecha_publicacion, PiezaContenido.created_at
                )
            )
        )

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

    def por_token(self, token: str) -> EncuestaSatisfaccion | None:
        return self.s.scalar(
            select(EncuestaSatisfaccion).where(
                EncuestaSatisfaccion.token_publico == token
            )
        )

    def abierta_de_telefono(self, telefono: str) -> EncuestaSatisfaccion | None:
        """La encuesta en curso de ese número. La más reciente: si al mismo
        teléfono se le mandaron dos, lo que el cliente está contestando ahora
        es la última que le llegó."""
        return self.s.scalar(
            select(EncuestaSatisfaccion)
            .where(
                EncuestaSatisfaccion.destino == telefono,
                EncuestaSatisfaccion.estado == "enviada",
            )
            .order_by(EncuestaSatisfaccion.fecha_envio.desc())
            .limit(1)
        )

    def vencidas(self, ahora: datetime, limite: int = 500) -> list[EncuestaSatisfaccion]:
        return list(
            self.s.scalars(
                select(EncuestaSatisfaccion)
                .where(
                    EncuestaSatisfaccion.estado == "enviada",
                    EncuestaSatisfaccion.fecha_expiracion <= ahora,
                )
                .limit(limite)
            )
        )

    def respuesta_de(
        self, encuesta_id: uuid.UUID, pregunta_id: uuid.UUID
    ) -> EncuestaRespuesta | None:
        return self.s.scalar(
            select(EncuestaRespuesta).where(
                EncuestaRespuesta.encuesta_id == encuesta_id,
                EncuestaRespuesta.pregunta_id == pregunta_id,
            )
        )

    def respuestas_de(self, encuesta_id: uuid.UUID) -> list[EncuestaRespuesta]:
        return list(
            self.s.scalars(
                select(EncuestaRespuesta)
                .where(EncuestaRespuesta.encuesta_id == encuesta_id)
                .order_by(EncuestaRespuesta.created_at)
            )
        )

    def add(self, encuesta: EncuestaSatisfaccion) -> EncuestaSatisfaccion:
        self.s.add(encuesta)
        self.s.flush()
        return encuesta


class EncuestaPlantillaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, plantilla_id: uuid.UUID) -> EncuestaPlantilla | None:
        return self.s.get(EncuestaPlantilla, plantilla_id)

    def activa_de_empresa(self, empresa_id: uuid.UUID) -> EncuestaPlantilla | None:
        return self.s.scalar(
            select(EncuestaPlantilla).where(
                EncuestaPlantilla.empresa_id == empresa_id,
                EncuestaPlantilla.activa.is_(True),
                EncuestaPlantilla.deleted_at.is_(None),
            )
        )

    def activas_de_empresa(self, empresa_id: uuid.UUID) -> list[EncuestaPlantilla]:
        return list(
            self.s.scalars(
                select(EncuestaPlantilla).where(
                    EncuestaPlantilla.empresa_id == empresa_id,
                    EncuestaPlantilla.activa.is_(True),
                    EncuestaPlantilla.deleted_at.is_(None),
                )
            )
        )

    def q_listar(self, empresa_id: uuid.UUID | None):
        stmt = select(EncuestaPlantilla).where(EncuestaPlantilla.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(EncuestaPlantilla.empresa_id == empresa_id)
        return stmt.order_by(EncuestaPlantilla.created_at.desc())

    def pregunta(self, pregunta_id: uuid.UUID) -> EncuestaPregunta | None:
        return self.s.get(EncuestaPregunta, pregunta_id)

    def preguntas_de(self, plantilla_id: uuid.UUID) -> list[EncuestaPregunta]:
        return list(
            self.s.scalars(
                select(EncuestaPregunta)
                .where(EncuestaPregunta.plantilla_id == plantilla_id)
                .order_by(EncuestaPregunta.orden)
            )
        )

    def pregunta_por_codigo(
        self, plantilla_id: uuid.UUID, codigo: str
    ) -> EncuestaPregunta | None:
        return self.s.scalar(
            select(EncuestaPregunta).where(
                EncuestaPregunta.plantilla_id == plantilla_id,
                EncuestaPregunta.codigo == codigo,
            )
        )

    def add(self, plantilla: EncuestaPlantilla) -> EncuestaPlantilla:
        self.s.add(plantilla)
        self.s.flush()
        return plantilla


class EvaluacionAgenciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, evaluacion_id: uuid.UUID) -> EvaluacionAgencia | None:
        return self.s.get(EvaluacionAgencia, evaluacion_id)

    def q_de_campana(self, campana_id: uuid.UUID):
        return (
            select(EvaluacionAgencia)
            .where(EvaluacionAgencia.campana_id == campana_id)
            .order_by(EvaluacionAgencia.created_at.desc())
        )

    def add(self, evaluacion: EvaluacionAgencia) -> EvaluacionAgencia:
        self.s.add(evaluacion)
        self.s.flush()
        return evaluacion


class CampanaMetricaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def de_campana(self, campana_id: uuid.UUID) -> CampanaMetrica | None:
        return self.s.scalar(
            select(CampanaMetrica).where(CampanaMetrica.campana_id == campana_id)
        )

    def obtener_o_crear(self, campana_id: uuid.UUID) -> CampanaMetrica:
        fila = self.de_campana(campana_id)
        if fila is None:
            fila = CampanaMetrica(campana_id=campana_id)
            self.s.add(fila)
            self.s.flush()
        return fila
