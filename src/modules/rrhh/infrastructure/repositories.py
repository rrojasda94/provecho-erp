"""Repositorios SQLAlchemy del módulo rrhh. La sesión es la Unit of Work."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.rrhh.infrastructure.models import (
    Acta,
    Amonestacion,
    Asistencia,
    BoletaPago,
    CertificadoTrabajo,
    ContratoLaboral,
    Convocatoria,
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

    def q_list(self, empresa_id: uuid.UUID | None = None):
        """La consulta, sin ejecutar: el router la pagina (ADR-026)."""
        q = select(Trabajador).where(Trabajador.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Trabajador.empresa_id == empresa_id)
        return q.order_by(Trabajador.created_at.desc())

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Trabajador]:
        return list(self.s.scalars(self.q_list(empresa_id)))

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


class ConvocatoriaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, convocatoria_id: uuid.UUID) -> Convocatoria | None:
        return self.s.get(Convocatoria, convocatoria_id)

    def get_por_token(self, token: str) -> Convocatoria | None:
        return self.s.scalar(
            select(Convocatoria).where(
                Convocatoria.token_publico == token, Convocatoria.deleted_at.is_(None)
            )
        )

    def list(
        self, empresa_id: uuid.UUID | None = None, estado: str | None = None
    ) -> list[Convocatoria]:
        q = select(Convocatoria).where(Convocatoria.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Convocatoria.empresa_id == empresa_id)
        if estado is not None:
            q = q.where(Convocatoria.estado == estado)
        return list(self.s.scalars(q))

    def add(self, convocatoria: Convocatoria) -> Convocatoria:
        self.s.add(convocatoria)
        self.s.flush()
        return convocatoria


class PostulanteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, postulante_id: uuid.UUID) -> Postulante | None:
        return self.s.get(Postulante, postulante_id)

    def q_list(
        self,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
        convocatoria_id: uuid.UUID | None = None,
    ):
        q = select(Postulante).where(Postulante.deleted_at.is_(None))
        if estado is not None:
            q = q.where(Postulante.estado == estado)
        if empresa_id is not None:
            q = q.where(Postulante.empresa_id == empresa_id)
        if convocatoria_id is not None:
            q = q.where(Postulante.convocatoria_id == convocatoria_id)
        return q.order_by(Postulante.fecha_postulacion)

    def list(
        self,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
        convocatoria_id: uuid.UUID | None = None,
    ) -> list[Postulante]:
        return list(
            self.s.scalars(self.q_list(estado, empresa_id, convocatoria_id))
        )

    def add(self, postulante: Postulante) -> Postulante:
        self.s.add(postulante)
        self.s.flush()
        return postulante


class SocioRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, socio_id: uuid.UUID) -> Socio | None:
        return self.s.get(Socio, socio_id)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Socio]:
        """Filtrar por empresa incluye a los socios del grupo (`empresa_id`
        NULL): participan del grupo entero, no de una sola empresa."""
        q = select(Socio).where(Socio.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(
                (Socio.empresa_id == empresa_id) | (Socio.empresa_id.is_(None))
            )
        return list(self.s.scalars(q))

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

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[LiquidacionBss]:
        return list(
            self.s.scalars(
                select(LiquidacionBss)
                .where(LiquidacionBss.trabajador_id == trabajador_id)
                .order_by(LiquidacionBss.fecha_pago.desc())
            )
        )

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

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[Memorandum]:
        """Los dirigidos a esa persona. Un memorándum puede ir a un área
        entera (`destinatario_trabajador_id` NULL) y ese no es de nadie en
        particular: no entra en el legajo de nadie."""
        return list(
            self.s.scalars(
                select(Memorandum)
                .where(Memorandum.destinatario_trabajador_id == trabajador_id)
                .order_by(Memorandum.fecha.desc())
            )
        )

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

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[CertificadoTrabajo]:
        return list(
            self.s.scalars(
                select(CertificadoTrabajo)
                .where(CertificadoTrabajo.trabajador_id == trabajador_id)
                .order_by(CertificadoTrabajo.fecha_emision.desc())
            )
        )

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

    # Ver la nota de `TrabajadorRepo.q_list`: este método sombrea al builtin.
    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        estado: str | None = None,
        trabajador_id: uuid.UUID | None = None,
    ):
        """La bandeja de aprobación, sin ejecutar (ADR-026).

        Se filtra por empresa a través de `trabajador`: `solicitud_permiso`
        no la tiene y agregársela duplicaría un dato que ya vive un salto
        más allá — el trabajador es de una sola empresa por definición.
        """
        q = select(SolicitudPermiso)
        if empresa_id is not None:
            q = q.join(
                Trabajador, Trabajador.id == SolicitudPermiso.trabajador_id
            ).where(Trabajador.empresa_id == empresa_id)
        if estado is not None:
            q = q.where(SolicitudPermiso.estado == estado)
        if trabajador_id is not None:
            q = q.where(SolicitudPermiso.trabajador_id == trabajador_id)
        # Las más viejas primero: una solicitud de vacaciones que envejece
        # sin respuesta es la que hay que atender, no la última que entró.
        return q.order_by(SolicitudPermiso.fecha_desde)

    def add(self, solicitud: SolicitudPermiso) -> SolicitudPermiso:
        self.s.add(solicitud)
        self.s.flush()
        return solicitud


class PactoPermanenciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, pacto_id: uuid.UUID) -> PactoPermanencia | None:
        return self.s.get(PactoPermanencia, pacto_id)

    def list_por_trabajador(self, trabajador_id: uuid.UUID) -> list[PactoPermanencia]:
        return list(
            self.s.scalars(
                select(PactoPermanencia)
                .where(PactoPermanencia.trabajador_id == trabajador_id)
                .order_by(PactoPermanencia.fecha_inicio.desc())
            )
        )

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

    # Ver la nota de `TrabajadorRepo.q_list`: este método sombrea al builtin.
    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        trabajador_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ):
        """Marcaciones del rango, sin ejecutar (ADR-026).

        Es la única tabla del legajo que crece sin techo —una fila por día y
        por trabajador— y por eso no viaja dentro del legajo: se pide
        siempre acotada por rango.
        """
        q = select(Asistencia)
        if empresa_id is not None:
            q = q.join(Trabajador, Trabajador.id == Asistencia.trabajador_id).where(
                Trabajador.empresa_id == empresa_id
            )
        if trabajador_id is not None:
            q = q.where(Asistencia.trabajador_id == trabajador_id)
        if desde is not None:
            q = q.where(Asistencia.fecha >= desde)
        if hasta is not None:
            q = q.where(Asistencia.fecha <= hasta)
        return q.order_by(Asistencia.fecha.desc())

    def add(self, asistencia: Asistencia) -> Asistencia:
        self.s.add(asistencia)
        self.s.flush()
        return asistencia
