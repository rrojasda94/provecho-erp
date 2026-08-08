"""Acumulado por campaña, alimentado por los eventos que marketing publica.

Hasta 2026-08-08 `marketing.campana_lanzada` y `marketing.lead_generado` se
publicaban y **nadie los escuchaba**: el módulo emitía al vacío. Acá está el
consumidor, y es el propio módulo — la campaña es de marketing, y quien sabe
qué significa "convertido" es marketing, no BI.

Lo que se acumula no es lo que ya está en las tablas por conveniencia: es la
respuesta a "¿esta campaña sirvió?", que cruza cuatro entidades (lead, venta
atribuida, pieza publicada y encuesta del cliente que la campaña trajo) y
que reconstruida a mano cuesta cuatro consultas cada vez que alguien abre el
tablero.

Derivado y reconstruible: si se corrompe, `recalcular` lo rehace desde las
tablas. No es fuente de verdad de nada.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.marketing.infrastructure.models import (
    CampanaMetrica,
    EncuestaSatisfaccion,
    Lead,
    PiezaContenido,
)
from src.modules.marketing.infrastructure.repositories import (
    CampanaMetricaRepo,
    LeadRepo,
)
from src.shared import fechas


def registrar_lanzamiento(session: Session, campana_id: uuid.UUID) -> CampanaMetrica:
    metrica = CampanaMetricaRepo(session).obtener_o_crear(campana_id)
    metrica.fecha_lanzamiento = metrica.fecha_lanzamiento or fechas.hoy()
    session.flush()
    return metrica


def sumar_lead(session: Session, campana_id: uuid.UUID) -> CampanaMetrica:
    metrica = CampanaMetricaRepo(session).obtener_o_crear(campana_id)
    metrica.leads_generados += 1
    session.flush()
    return metrica


def sumar_conversion(session: Session, campana_id: uuid.UUID) -> CampanaMetrica:
    metrica = CampanaMetricaRepo(session).obtener_o_crear(campana_id)
    metrica.leads_convertidos += 1
    session.flush()
    return metrica


def sumar_pieza(session: Session, campana_id: uuid.UUID) -> CampanaMetrica:
    metrica = CampanaMetricaRepo(session).obtener_o_crear(campana_id)
    metrica.piezas_publicadas += 1
    session.flush()
    return metrica


def sumar_encuesta_enviada(session: Session, venta_id: uuid.UUID) -> CampanaMetrica | None:
    """Acredita la encuesta a la campaña que trajo esa venta, si la hubo.

    La encuesta no cuelga de una campaña: cuelga de una venta. El puente es
    el lead atribuido — y por eso una encuesta de un cliente que llegó solo
    no le suma a ninguna campaña, que es exactamente lo correcto.
    """
    campana_id = LeadRepo(session).campana_de_venta(venta_id)
    if campana_id is None:
        return None
    metrica = CampanaMetricaRepo(session).obtener_o_crear(campana_id)
    metrica.encuestas_enviadas += 1
    session.flush()
    return metrica


def sumar_encuesta_respondida(
    session: Session, venta_id: uuid.UUID, puntaje: int | None
) -> CampanaMetrica | None:
    campana_id = LeadRepo(session).campana_de_venta(venta_id)
    if campana_id is None:
        return None
    metrica = CampanaMetricaRepo(session).obtener_o_crear(campana_id)
    metrica.encuestas_respondidas += 1
    metrica.puntaje_suma += puntaje or 0
    session.flush()
    return metrica


def resumen(session: Session, campana_id: uuid.UUID) -> dict:
    """Lo acumulado más lo que se deriva de ello (conversión y puntaje
    promedio se calculan al leer: guardarlos obligaría a recalcular dos
    campos cada vez que cambia uno)."""
    metrica = CampanaMetricaRepo(session).de_campana(campana_id) or CampanaMetrica(
        campana_id=campana_id
    )
    generados = metrica.leads_generados or 0
    respondidas = metrica.encuestas_respondidas or 0
    return {
        "campana_id": campana_id,
        "fecha_lanzamiento": metrica.fecha_lanzamiento,
        "leads_generados": generados,
        "leads_convertidos": metrica.leads_convertidos or 0,
        "piezas_publicadas": metrica.piezas_publicadas or 0,
        "encuestas_enviadas": metrica.encuestas_enviadas or 0,
        "encuestas_respondidas": respondidas,
        "tasa_conversion": (
            round((metrica.leads_convertidos or 0) / generados, 4) if generados else None
        ),
        "puntaje_promedio": (
            round((metrica.puntaje_suma or 0) / respondidas, 2) if respondidas else None
        ),
    }


def recalcular(session: Session, campana_id: uuid.UUID) -> CampanaMetrica:
    """Rehace el acumulado desde las tablas. Es la red de seguridad del
    diseño: un evento perdido (worker caído, listener que reventó) deja el
    contador corto y sin esto no habría forma de corregirlo."""
    metrica = CampanaMetricaRepo(session).obtener_o_crear(campana_id)
    metrica.leads_generados = _contar(session, Lead.campana_id == campana_id)
    metrica.leads_convertidos = _contar(
        session, Lead.campana_id == campana_id, Lead.venta_id.isnot(None)
    )
    metrica.piezas_publicadas = session.scalar(
        select(func.count(PiezaContenido.id)).where(
            PiezaContenido.campana_id == campana_id,
            PiezaContenido.estado == "publicada",
        )
    )
    ventas = select(Lead.venta_id).where(
        Lead.campana_id == campana_id, Lead.venta_id.isnot(None)
    )
    metrica.encuestas_enviadas = session.scalar(
        select(func.count(EncuestaSatisfaccion.id)).where(
            EncuestaSatisfaccion.venta_id.in_(ventas)
        )
    )
    metrica.encuestas_respondidas = session.scalar(
        select(func.count(EncuestaSatisfaccion.id)).where(
            EncuestaSatisfaccion.venta_id.in_(ventas),
            EncuestaSatisfaccion.estado == "respondida",
        )
    )
    metrica.puntaje_suma = session.scalar(
        select(func.coalesce(func.sum(EncuestaSatisfaccion.puntaje), 0)).where(
            EncuestaSatisfaccion.venta_id.in_(ventas)
        )
    )
    session.flush()
    return metrica


def _contar(session: Session, *condiciones) -> int:
    return session.scalar(select(func.count(Lead.id)).where(*condiciones)) or 0
