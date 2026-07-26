"""Repositorios SQLAlchemy del módulo rrhh. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.rrhh.infrastructure.models import (
    Acta,
    Amonestacion,
    Asistencia,
    BoletaPago,
    CertificadoTrabajo,
    ContratoLaboral,
    LiquidacionBss,
    Memorandum,
    PactoPermanencia,
    Postulante,
    Socio,
    SolicitudPermiso,
    Trabajador,
)


class TrabajadorRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, trabajador_id: uuid.UUID) -> Trabajador | None:
        return self.s.get(Trabajador, trabajador_id)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Trabajador]:
        q = select(Trabajador).where(Trabajador.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Trabajador.empresa_id == empresa_id)
        return list(self.s.scalars(q))

    def add(self, trabajador: Trabajador) -> Trabajador:
        self.s.add(trabajador)
        self.s.flush()
        return trabajador


class ContratoLaboralRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, contrato_id: uuid.UUID) -> ContratoLaboral | None:
        return self.s.get(ContratoLaboral, contrato_id)

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[ContratoLaboral]:
        return list(
            self.s.scalars(
                select(ContratoLaboral).where(ContratoLaboral.trabajador_id == trabajador_id)
            )
        )

    def add(self, contrato: ContratoLaboral) -> ContratoLaboral:
        self.s.add(contrato)
        self.s.flush()
        return contrato


class PostulanteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, postulante_id: uuid.UUID) -> Postulante | None:
        return self.s.get(Postulante, postulante_id)

    def list(self, estado: str | None = None) -> list[Postulante]:
        q = select(Postulante).where(Postulante.deleted_at.is_(None))
        if estado is not None:
            q = q.where(Postulante.estado == estado)
        return list(self.s.scalars(q))

    def add(self, postulante: Postulante) -> Postulante:
        self.s.add(postulante)
        self.s.flush()
        return postulante


class SocioRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, socio_id: uuid.UUID) -> Socio | None:
        return self.s.get(Socio, socio_id)

    def list(self) -> list[Socio]:
        return list(self.s.scalars(select(Socio).where(Socio.deleted_at.is_(None))))

    def add(self, socio: Socio) -> Socio:
        self.s.add(socio)
        self.s.flush()
        return socio


class BoletaPagoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, boleta_id: uuid.UUID) -> BoletaPago | None:
        return self.s.get(BoletaPago, boleta_id)

    def get_by_idempotency(self, idempotency_key: str) -> BoletaPago | None:
        return self.s.scalar(
            select(BoletaPago).where(BoletaPago.idempotency_key == idempotency_key)
        )

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[BoletaPago]:
        return list(
            self.s.scalars(select(BoletaPago).where(BoletaPago.trabajador_id == trabajador_id))
        )

    def add(self, boleta: BoletaPago) -> BoletaPago:
        self.s.add(boleta)
        self.s.flush()
        return boleta


class LiquidacionBssRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, liquidacion_id: uuid.UUID) -> LiquidacionBss | None:
        return self.s.get(LiquidacionBss, liquidacion_id)

    def get_by_idempotency(self, idempotency_key: str) -> LiquidacionBss | None:
        return self.s.scalar(
            select(LiquidacionBss).where(LiquidacionBss.idempotency_key == idempotency_key)
        )

    def add(self, liquidacion: LiquidacionBss) -> LiquidacionBss:
        self.s.add(liquidacion)
        self.s.flush()
        return liquidacion


class MemorandumRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, memorandum_id: uuid.UUID) -> Memorandum | None:
        return self.s.get(Memorandum, memorandum_id)

    def add(self, memorandum: Memorandum) -> Memorandum:
        self.s.add(memorandum)
        self.s.flush()
        return memorandum


class AmonestacionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, amonestacion_id: uuid.UUID) -> Amonestacion | None:
        return self.s.get(Amonestacion, amonestacion_id)

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[Amonestacion]:
        return list(
            self.s.scalars(
                select(Amonestacion).where(Amonestacion.trabajador_id == trabajador_id)
            )
        )

    def add(self, amonestacion: Amonestacion) -> Amonestacion:
        self.s.add(amonestacion)
        self.s.flush()
        return amonestacion


class ActaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, acta_id: uuid.UUID) -> Acta | None:
        return self.s.get(Acta, acta_id)

    def add(self, acta: Acta) -> Acta:
        self.s.add(acta)
        self.s.flush()
        return acta


class CertificadoTrabajoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, certificado_id: uuid.UUID) -> CertificadoTrabajo | None:
        return self.s.get(CertificadoTrabajo, certificado_id)

    def add(self, certificado: CertificadoTrabajo) -> CertificadoTrabajo:
        self.s.add(certificado)
        self.s.flush()
        return certificado


class SolicitudPermisoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, solicitud_id: uuid.UUID) -> SolicitudPermiso | None:
        return self.s.get(SolicitudPermiso, solicitud_id)

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[SolicitudPermiso]:
        return list(
            self.s.scalars(
                select(SolicitudPermiso).where(SolicitudPermiso.trabajador_id == trabajador_id)
            )
        )

    def add(self, solicitud: SolicitudPermiso) -> SolicitudPermiso:
        self.s.add(solicitud)
        self.s.flush()
        return solicitud


class PactoPermanenciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, pacto_id: uuid.UUID) -> PactoPermanencia | None:
        return self.s.get(PactoPermanencia, pacto_id)

    def add(self, pacto: PactoPermanencia) -> PactoPermanencia:
        self.s.add(pacto)
        self.s.flush()
        return pacto


class AsistenciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, asistencia_id: uuid.UUID) -> Asistencia | None:
        return self.s.get(Asistencia, asistencia_id)

    def get_por_trabajador_fecha(self, trabajador_id: uuid.UUID, fecha) -> Asistencia | None:
        return self.s.scalar(
            select(Asistencia).where(
                Asistencia.trabajador_id == trabajador_id, Asistencia.fecha == fecha
            )
        )

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[Asistencia]:
        return list(
            self.s.scalars(select(Asistencia).where(Asistencia.trabajador_id == trabajador_id))
        )

    def add(self, asistencia: Asistencia) -> Asistencia:
        self.s.add(asistencia)
        self.s.flush()
        return asistencia
