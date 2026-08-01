"""Casos de uso de documentos de RRHH: `memorandum`, `amonestacion`, `acta`,
`certificado_trabajo`. Emisión — no hay flujo de estado, son documentos
firmados en el momento (RN-RRHH-004/007)."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.rrhh.application.errors import NoEncontrado, ReglaNegocio
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import (
    Acta,
    Amonestacion,
    CertificadoTrabajo,
    Memorandum,
)
from src.modules.rrhh.infrastructure.repositories import (
    ActaRepo,
    AmonestacionRepo,
    CertificadoTrabajoRepo,
    MemorandumRepo,
    TrabajadorRepo,
)
from src.modules.users.infrastructure.models import Empresa


def emitir_memorandum(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    emisor_id: uuid.UUID,
    asunto: str,
    cuerpo: str,
    fecha: date,
    destinatario_trabajador_id: uuid.UUID | None = None,
    destinatario_area: str | None = None,
) -> Memorandum:
    if destinatario_trabajador_id is None and not destinatario_area:
        raise ReglaNegocio("memorándum requiere destinatario_trabajador_id o destinatario_area")
    if session.get(Empresa, empresa_id) is None:
        raise NoEncontrado(f"empresa {empresa_id} no encontrada")
    return MemorandumRepo(session).add(
        Memorandum(
            empresa_id=empresa_id,
            emisor_id=emisor_id,
            destinatario_trabajador_id=destinatario_trabajador_id,
            destinatario_area=destinatario_area,
            asunto=asunto,
            cuerpo=cuerpo,
            fecha=fecha,
        )
    )


def emitir_amonestacion(
    session: Session,
    *,
    trabajador_id: uuid.UUID,
    tipo: str,
    falta: str,
    fecha_hecho: date,
    fecha_emision: date,
    emisor_id: uuid.UUID,
    descargo: str | None = None,
    descargo_plazo_dias: int | None = None,
    sancion_relacionada: str | None = None,
) -> Amonestacion:
    if tipo not in ("verbal", "escrita"):
        raise ReglaNegocio(f"tipo de amonestación inválido: {tipo}")
    if TrabajadorRepo(session).get(trabajador_id) is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")
    amonestacion = AmonestacionRepo(session).add(
        Amonestacion(
            trabajador_id=trabajador_id,
            tipo=tipo,
            falta=falta,
            fecha_hecho=fecha_hecho,
            fecha_emision=fecha_emision,
            emisor_id=emisor_id,
            descargo=descargo,
            descargo_plazo_dias=descargo_plazo_dias,
            sancion_relacionada=sancion_relacionada,
        )
    )
    event_bus.publish(
        "rrhh.amonestacion_emitida",
        {
            "amonestacion_id": str(amonestacion.id),
            "trabajador_id": str(trabajador_id),
            "tipo": tipo,
        },
        session=session,
    )
    return amonestacion


def emitir_acta(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    tipo: str,
    fecha: date,
    lugar: str,
    hechos: str,
    participantes: list,
) -> Acta:
    if session.get(Empresa, empresa_id) is None:
        raise NoEncontrado(f"empresa {empresa_id} no encontrada")
    return ActaRepo(session).add(
        Acta(
            empresa_id=empresa_id,
            tipo=tipo,
            fecha=fecha,
            lugar=lugar,
            hechos=hechos,
            participantes=participantes,
        )
    )


def emitir_certificado_trabajo(
    session: Session,
    *,
    trabajador_id: uuid.UUID,
    fecha_emision: date,
    cargos: str,
    conducta_desempeno: str | None = None,
) -> CertificadoTrabajo:
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")
    fecha_referencia = trabajador.fecha_cese or fecha_emision
    tiempo_servicios_meses = rules.meses_servicio(trabajador.fecha_ingreso, fecha_referencia)
    dentro_de_plazo = (
        rules.dentro_de_plazo_horas(trabajador.fecha_cese, fecha_emision)
        if trabajador.fecha_cese is not None
        else True
    )
    return CertificadoTrabajoRepo(session).add(
        CertificadoTrabajo(
            trabajador_id=trabajador_id,
            fecha_emision=fecha_emision,
            tiempo_servicios_meses=tiempo_servicios_meses,
            cargos=cargos,
            conducta_desempeno=conducta_desempeno,
            dentro_de_plazo=dentro_de_plazo,
        )
    )
