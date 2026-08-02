"""Casos de uso de encuesta de satisfacción: enviarla sobre una venta ya
entregada y registrar la respuesta.

Selectiva a propósito (RN-COM-007): Marketing elige a qué venta entregada
le manda encuesta. No hay envío automático masivo. El estado de entrega se
lee por el contrato público de `sales` — marketing no toca `Venta`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.marketing.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.marketing.domain import rules
from src.modules.marketing.infrastructure.models import EncuestaSatisfaccion
from src.modules.marketing.infrastructure.repositories import EncuestaRepo
from src.modules.sales.application.queries_publicas import venta_para_encuesta


def enviar_encuesta(
    session: Session,
    *,
    venta_id: uuid.UUID,
    canal: str,
    enviada_por: uuid.UUID,
) -> EncuestaSatisfaccion:
    repo = EncuestaRepo(session)
    existente = repo.de_venta(venta_id)
    if existente is not None:
        return existente

    venta = venta_para_encuesta(session, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if not venta["entregada"]:
        raise Conflicto(
            "el pedido todavía no se entregó; la encuesta se envía después de "
            "la entrega (PROC-OPE-002)"
        )
    if venta["cliente_id"] is None:
        raise ReglaNegocio("la venta no tiene cliente registrado; no hay a quién encuestar")

    encuesta = repo.add(
        EncuestaSatisfaccion(
            venta_id=venta_id,
            cliente_id=venta["cliente_id"],
            canal=canal,
            estado="enviada",
            enviada_por=enviada_por,
        )
    )
    event_bus.publish(
        "marketing.encuesta_enviada",
        {
            "encuesta_id": str(encuesta.id),
            "venta_id": str(venta_id),
            "cliente_id": str(venta["cliente_id"]),
            "canal": canal,
        },
    )
    return encuesta


def registrar_respuesta(
    session: Session,
    encuesta_id: uuid.UUID,
    *,
    puntaje: int,
    comentario: str | None = None,
) -> EncuestaSatisfaccion:
    encuesta = _encuesta(session, encuesta_id)
    if encuesta.estado != "enviada":
        raise Conflicto(f"la encuesta está {encuesta.estado}; no admite respuesta")
    if not rules.puntaje_valido(puntaje):
        raise ReglaNegocio(
            f"puntaje fuera de rango ({rules.PUNTAJE_MIN}-{rules.PUNTAJE_MAX})"
        )
    encuesta.puntaje = puntaje
    encuesta.comentario = comentario
    encuesta.fecha_respuesta = datetime.now(UTC)
    encuesta.estado = "respondida"
    session.flush()
    return encuesta


def expirar_encuesta(session: Session, encuesta_id: uuid.UUID) -> EncuestaSatisfaccion:
    encuesta = _encuesta(session, encuesta_id)
    if encuesta.estado != "enviada":
        raise Conflicto(f"la encuesta está {encuesta.estado}; no admite expiración")
    encuesta.estado = "expirada"
    session.flush()
    return encuesta


def _encuesta(session: Session, encuesta_id: uuid.UUID) -> EncuestaSatisfaccion:
    encuesta = EncuestaRepo(session).get(encuesta_id)
    if encuesta is None:
        raise NoEncontrado("encuesta no encontrada")
    return encuesta
