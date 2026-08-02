"""Casos de uso de contenido: planificar la pieza en el calendario y
publicarla solo si es pertinente a la marca y su uso de marca está validado
(RN-MKT-001/002). Contenido viral pero ajeno a la marca no se publica.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from src.modules.marketing.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.marketing.domain import rules
from src.modules.marketing.infrastructure.models import Campana, PiezaContenido
from src.modules.marketing.infrastructure.repositories import PiezaContenidoRepo
from src.modules.users.infrastructure.models import Marca


def planificar_pieza(
    session: Session,
    *,
    marca_id: uuid.UUID,
    titulo: str,
    canal: str,
    fecha_publicacion: date,
    creado_por: uuid.UUID,
    campana_id: uuid.UUID | None = None,
    pertinente_marca: bool = False,
    uso_marca_validado: bool = False,
) -> PiezaContenido:
    if session.get(Marca, marca_id) is None:
        raise NoEncontrado(f"marca {marca_id} no encontrada")
    if campana_id is not None and session.get(Campana, campana_id) is None:
        raise NoEncontrado(f"campaña {campana_id} no encontrada")

    return PiezaContenidoRepo(session).add(
        PiezaContenido(
            campana_id=campana_id,
            marca_id=marca_id,
            titulo=titulo,
            canal=canal,
            fecha_publicacion=fecha_publicacion,
            pertinente_marca=pertinente_marca,
            uso_marca_validado=uso_marca_validado,
            estado="planificada",
            creado_por=creado_por,
        )
    )


def validar_pieza(
    session: Session,
    pieza_id: uuid.UUID,
    *,
    pertinente_marca: bool | None = None,
    uso_marca_validado: bool | None = None,
) -> PiezaContenido:
    pieza = _pieza(session, pieza_id)
    if pieza.estado != "planificada":
        raise Conflicto(f"la pieza está {pieza.estado}; ya no admite validación")
    if pertinente_marca is not None:
        pieza.pertinente_marca = pertinente_marca
    if uso_marca_validado is not None:
        pieza.uso_marca_validado = uso_marca_validado
    session.flush()
    return pieza


def publicar_pieza(
    session: Session, pieza_id: uuid.UUID, *, metricas: dict | None = None
) -> PiezaContenido:
    pieza = _pieza(session, pieza_id)
    if pieza.estado != "planificada":
        raise Conflicto(f"la pieza está {pieza.estado}; no admite publicación")
    if not rules.puede_publicar(pieza):
        raise ReglaNegocio(
            "la pieza no es pertinente a la marca o su uso de marca no está "
            "validado (RN-MKT-001/002)"
        )
    pieza.estado = "publicada"
    if metricas is not None:
        pieza.metricas = metricas
    session.flush()
    return pieza


def descartar_pieza(session: Session, pieza_id: uuid.UUID) -> PiezaContenido:
    pieza = _pieza(session, pieza_id)
    if pieza.estado == "publicada":
        raise Conflicto("una pieza publicada no se descarta")
    pieza.estado = "descartada"
    session.flush()
    return pieza


def _pieza(session: Session, pieza_id: uuid.UUID) -> PiezaContenido:
    pieza = PiezaContenidoRepo(session).get(pieza_id)
    if pieza is None:
        raise NoEncontrado("pieza de contenido no encontrada")
    return pieza
