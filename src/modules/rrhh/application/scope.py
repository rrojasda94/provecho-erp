"""Validación de alcance de tenant sobre recursos de rrhh (ADR-004).

El trabajador lleva el `empresa_id`; todo lo que cuelga de él (contrato,
boleta, permiso, sanción, certificado, pacto) hereda su alcance. Los
documentos que se emiten a nombre de la empresa (memorándum, acta) lo
llevan directo.

`convocatoria` y `postulante` llevan `empresa_id` propio desde 2026-08-01:
la contratación es de la empresa, no del grupo (el grupo no tiene planilla).
"""

import uuid

from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.rrhh.application.errors import NoEncontrado
from src.modules.rrhh.infrastructure.models import (
    Acta,
    Amonestacion,
    BoletaPago,
    CertificadoTrabajo,
    ContratoLaboral,
    Convocatoria,
    LiquidacionBss,
    Memorandum,
    PactoPermanencia,
    Postulante,
    SolicitudPermiso,
    Trabajador,
    TurnoSucursal,
)


def exigir_trabajador(
    session: Session, trabajador_id: uuid.UUID, tenant: Tenant
) -> Trabajador:
    trabajador = session.get(Trabajador, trabajador_id)
    if trabajador is None or trabajador.deleted_at is not None:
        raise NoEncontrado("trabajador no encontrado")
    tenant.exigir_empresa(trabajador.empresa_id)
    return trabajador


def _de_trabajador(session: Session, modelo, obj_id, tenant: Tenant, faltante: str):
    obj = session.get(modelo, obj_id)
    if obj is None:
        raise NoEncontrado(faltante)
    exigir_trabajador(session, obj.trabajador_id, tenant)
    return obj


def exigir_contrato(
    session: Session, contrato_id: uuid.UUID, tenant: Tenant
) -> ContratoLaboral:
    return _de_trabajador(
        session, ContratoLaboral, contrato_id, tenant, "contrato no encontrado"
    )


def exigir_boleta(session: Session, boleta_id: uuid.UUID, tenant: Tenant) -> BoletaPago:
    return _de_trabajador(
        session, BoletaPago, boleta_id, tenant, "boleta de pago no encontrada"
    )


def exigir_liquidacion(
    session: Session, liquidacion_id: uuid.UUID, tenant: Tenant
) -> LiquidacionBss:
    return _de_trabajador(
        session, LiquidacionBss, liquidacion_id, tenant, "liquidación no encontrada"
    )


def exigir_amonestacion(
    session: Session, amonestacion_id: uuid.UUID, tenant: Tenant
) -> Amonestacion:
    return _de_trabajador(
        session, Amonestacion, amonestacion_id, tenant, "amonestación no encontrada"
    )


def exigir_certificado(
    session: Session, certificado_id: uuid.UUID, tenant: Tenant
) -> CertificadoTrabajo:
    return _de_trabajador(
        session, CertificadoTrabajo, certificado_id, tenant, "certificado no encontrado"
    )


def exigir_solicitud_permiso(
    session: Session, solicitud_id: uuid.UUID, tenant: Tenant
) -> SolicitudPermiso:
    return _de_trabajador(
        session, SolicitudPermiso, solicitud_id, tenant, "solicitud no encontrada"
    )


def exigir_pacto(
    session: Session, pacto_id: uuid.UUID, tenant: Tenant
) -> PactoPermanencia:
    return _de_trabajador(
        session, PactoPermanencia, pacto_id, tenant, "pacto de permanencia no encontrado"
    )


def exigir_memorandum(
    session: Session, memorandum_id: uuid.UUID, tenant: Tenant
) -> Memorandum:
    memorandum = session.get(Memorandum, memorandum_id)
    if memorandum is None:
        raise NoEncontrado("memorándum no encontrado")
    tenant.exigir_empresa(memorandum.empresa_id)
    return memorandum


def exigir_convocatoria(
    session: Session, convocatoria_id: uuid.UUID, tenant: Tenant
) -> Convocatoria:
    convocatoria = session.get(Convocatoria, convocatoria_id)
    if convocatoria is None or convocatoria.deleted_at is not None:
        raise NoEncontrado("convocatoria no encontrada")
    tenant.exigir_empresa(convocatoria.empresa_id)
    return convocatoria


def exigir_postulante(
    session: Session, postulante_id: uuid.UUID, tenant: Tenant
) -> Postulante:
    postulante = session.get(Postulante, postulante_id)
    if postulante is None or postulante.deleted_at is not None:
        raise NoEncontrado("postulante no encontrado")
    tenant.exigir_empresa(postulante.empresa_id)
    return postulante


def exigir_acta(session: Session, acta_id: uuid.UUID, tenant: Tenant) -> Acta:
    acta = session.get(Acta, acta_id)
    if acta is None:
        raise NoEncontrado("acta no encontrada")
    tenant.exigir_empresa(acta.empresa_id)
    return acta


def exigir_turno(
    session: Session, turno_id: uuid.UUID, tenant: Tenant
) -> TurnoSucursal:
    turno = session.get(TurnoSucursal, turno_id)
    if turno is None or turno.deleted_at is not None:
        raise NoEncontrado("turno no encontrado")
    tenant.exigir_sucursal(turno.sucursal_id)
    return turno
