"""Repositorios SQLAlchemy del módulo assets. La sesión es la Unit of Work."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.assets.infrastructure.models import (
    Activo,
    CargaCombustible,
    DocumentoVigencia,
    LecturaOdometro,
    OrdenMantenimiento,
    PlanMantenimiento,
    Vehiculo,
)
from src.shared.models import Comprobante


class ActivoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, activo_id: uuid.UUID) -> Activo | None:
        activo = self.s.get(Activo, activo_id)
        return activo if activo is not None and activo.deleted_at is None else None

    def add(self, activo: Activo) -> Activo:
        self.s.add(activo)
        self.s.flush()
        return activo

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        *,
        tipo: str | None = None,
        sucursal_id: uuid.UUID | None = None,
        incluir_archivados: bool = False,
    ):
        q = select(Activo).where(Activo.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Activo.empresa_id == empresa_id)
        if tipo is not None:
            q = q.where(Activo.tipo == tipo)
        if sucursal_id is not None:
            q = q.where(Activo.sucursal_id == sucursal_id)
        if not incluir_archivados:
            q = q.where(Activo.archivado.is_(False))
        return q.order_by(Activo.nombre)


class VehiculoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, activo_id: uuid.UUID) -> Vehiculo | None:
        return self.s.get(Vehiculo, activo_id)

    def get_by_placa(self, placa: str) -> Vehiculo | None:
        return self.s.scalar(select(Vehiculo).where(Vehiculo.placa == placa))

    def add(self, vehiculo: Vehiculo) -> Vehiculo:
        self.s.add(vehiculo)
        self.s.flush()
        return vehiculo


class LecturaOdometroRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, lectura: LecturaOdometro) -> LecturaOdometro:
        self.s.add(lectura)
        self.s.flush()
        return lectura

    def q_de_vehiculo(self, vehiculo_id: uuid.UUID):
        return (
            select(LecturaOdometro)
            .where(LecturaOdometro.vehiculo_id == vehiculo_id)
            .order_by(LecturaOdometro.fecha.desc(), LecturaOdometro.created_at.desc())
        )

    def list_de_vehiculo(self, vehiculo_id: uuid.UUID) -> list[LecturaOdometro]:
        return list(self.s.scalars(self.q_de_vehiculo(vehiculo_id)))


class CargaCombustibleRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, carga_id: uuid.UUID) -> CargaCombustible | None:
        return self.s.get(CargaCombustible, carga_id)

    def get_by_comprobante(self, comprobante_id: uuid.UUID) -> CargaCombustible | None:
        return self.s.scalar(
            select(CargaCombustible).where(CargaCombustible.comprobante_id == comprobante_id)
        )

    def add(self, carga: CargaCombustible) -> CargaCombustible:
        self.s.add(carga)
        self.s.flush()
        return carga

    def ultima_de_vehiculo(self, vehiculo_id: uuid.UUID) -> CargaCombustible | None:
        return self.s.scalar(
            select(CargaCombustible)
            .where(CargaCombustible.vehiculo_id == vehiculo_id)
            .order_by(CargaCombustible.fecha.desc(), CargaCombustible.created_at.desc())
        )

    def rendimientos_previos(self, vehiculo_id: uuid.UUID, *, limite: int) -> list:
        """Los últimos `limite` rendimientos conocidos, del más viejo al más
        nuevo (el orden que espera `domain.rules.es_consumo_anomalo`)."""
        filas = self.s.scalars(
            select(CargaCombustible.rendimiento_km_gal)
            .where(
                CargaCombustible.vehiculo_id == vehiculo_id,
                CargaCombustible.rendimiento_km_gal.is_not(None),
            )
            .order_by(CargaCombustible.fecha.desc(), CargaCombustible.created_at.desc())
            .limit(limite)
        ).all()
        return list(reversed(filas))

    def q_de_vehiculo(self, vehiculo_id: uuid.UUID):
        return (
            select(CargaCombustible)
            .where(CargaCombustible.vehiculo_id == vehiculo_id)
            .order_by(CargaCombustible.fecha.desc(), CargaCombustible.created_at.desc())
        )

    def list_de_vehiculo(self, vehiculo_id: uuid.UUID) -> list[CargaCombustible]:
        return list(self.s.scalars(self.q_de_vehiculo(vehiculo_id)))


class PlanMantenimientoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, plan_id: uuid.UUID) -> PlanMantenimiento | None:
        return self.s.get(PlanMantenimiento, plan_id)

    def add(self, plan: PlanMantenimiento) -> PlanMantenimiento:
        self.s.add(plan)
        self.s.flush()
        return plan

    def q_de_activo(self, activo_id: uuid.UUID):
        return (
            select(PlanMantenimiento)
            .where(PlanMantenimiento.activo_id == activo_id)
            .order_by(PlanMantenimiento.created_at)
        )

    def list_de_activo(self, activo_id: uuid.UUID) -> list[PlanMantenimiento]:
        return list(self.s.scalars(self.q_de_activo(activo_id)))

    def q_activos(self, empresa_id: uuid.UUID | None = None):
        """Planes activos, con su activo cargado — el barrido y el
        cronograma recorren esto sin N+1."""
        q = select(PlanMantenimiento).where(PlanMantenimiento.activo.is_(True))
        if empresa_id is not None:
            q = q.join(Activo, Activo.id == PlanMantenimiento.activo_id).where(
                Activo.empresa_id == empresa_id
            )
        return q

    def list_activos(self, empresa_id: uuid.UUID | None = None) -> list[PlanMantenimiento]:
        return list(self.s.scalars(self.q_activos(empresa_id)))


class OrdenMantenimientoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, orden_id: uuid.UUID) -> OrdenMantenimiento | None:
        return self.s.get(OrdenMantenimiento, orden_id)

    def add(self, orden: OrdenMantenimiento) -> OrdenMantenimiento:
        self.s.add(orden)
        self.s.flush()
        return orden

    def q_de_activo(self, activo_id: uuid.UUID):
        return (
            select(OrdenMantenimiento)
            .where(OrdenMantenimiento.activo_id == activo_id)
            .order_by(OrdenMantenimiento.created_at.desc())
        )

    def list_de_activo(self, activo_id: uuid.UUID) -> list[OrdenMantenimiento]:
        return list(self.s.scalars(self.q_de_activo(activo_id)))

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        *,
        estado: str | None = None,
        activo_id: uuid.UUID | None = None,
    ):
        q = select(OrdenMantenimiento).order_by(OrdenMantenimiento.created_at.desc())
        if empresa_id is not None:
            q = q.join(Activo, Activo.id == OrdenMantenimiento.activo_id).where(
                Activo.empresa_id == empresa_id
            )
        if estado is not None:
            q = q.where(OrdenMantenimiento.estado == estado)
        if activo_id is not None:
            q = q.where(OrdenMantenimiento.activo_id == activo_id)
        return q


class DocumentoVigenciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, documento_id: uuid.UUID) -> DocumentoVigencia | None:
        return self.s.get(DocumentoVigencia, documento_id)

    def add(self, documento: DocumentoVigencia) -> DocumentoVigencia:
        self.s.add(documento)
        self.s.flush()
        return documento

    def q_de_sujeto(self, sujeto_tipo: str, sujeto_id: uuid.UUID):
        return (
            select(DocumentoVigencia)
            .where(
                DocumentoVigencia.sujeto_tipo == sujeto_tipo,
                DocumentoVigencia.sujeto_id == sujeto_id,
            )
            .order_by(DocumentoVigencia.fecha_vencimiento.desc())
        )

    def list_de_sujeto(self, sujeto_tipo: str, sujeto_id: uuid.UUID) -> list[DocumentoVigencia]:
        return list(self.s.scalars(self.q_de_sujeto(sujeto_tipo, sujeto_id)))

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        *,
        sujeto_tipo: str | None = None,
        sujeto_id: uuid.UUID | None = None,
    ):
        q = select(DocumentoVigencia).order_by(DocumentoVigencia.fecha_vencimiento)
        if empresa_id is not None:
            q = q.where(DocumentoVigencia.empresa_id == empresa_id)
        if sujeto_tipo is not None:
            q = q.where(DocumentoVigencia.sujeto_tipo == sujeto_tipo)
        if sujeto_id is not None:
            q = q.where(DocumentoVigencia.sujeto_id == sujeto_id)
        return q

    def q_vigentes(self, empresa_id: uuid.UUID | None = None):
        """Sin renovar (`renovado_por_id IS NULL`) — el barrido y el
        cronograma solo miran la punta viva de la cadena de renovaciones."""
        q = self.q_list(empresa_id).where(DocumentoVigencia.renovado_por_id.is_(None))
        return q

    def list_vigentes(self, empresa_id: uuid.UUID | None = None) -> list[DocumentoVigencia]:
        return list(self.s.scalars(self.q_vigentes(empresa_id)))


def q_comprobantes_disponibles(
    empresa_id: uuid.UUID,
    *,
    desde: date | None = None,
    hasta: date | None = None,
):
    """Comprobantes recibidos de la empresa que todavía no sustentan ni una
    carga de combustible ni una orden de mantenimiento — lo que la pantalla
    de alta ofrece para elegir. No es un método de un repo de una sola tabla
    porque cruza `Comprobante` (shared) con dos tablas propias."""
    usados_en_carga = select(CargaCombustible.comprobante_id)
    usados_en_orden = select(OrdenMantenimiento.comprobante_id).where(
        OrdenMantenimiento.comprobante_id.is_not(None)
    )
    q = select(Comprobante).where(
        Comprobante.direccion == "recibido",
        Comprobante.empresa_id == empresa_id,
        Comprobante.id.not_in(usados_en_carga),
        Comprobante.id.not_in(usados_en_orden),
    )
    if desde is not None:
        q = q.where(Comprobante.fecha_emision >= desde)
    if hasta is not None:
        q = q.where(Comprobante.fecha_emision <= hasta)
    return q.order_by(Comprobante.created_at.desc())
