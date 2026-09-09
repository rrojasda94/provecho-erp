"""Repositorios SQLAlchemy del módulo production. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.production.infrastructure.models import (
    ChecklistInocuidadTurno,
    ConsumoProduccionItem,
    OrdenProduccion,
    OrdenProduccionTrabajador,
    PlanProduccion,
    ReporteProduccion,
)

# `Almacen` es organización transversal (data-model §1) y vive en `users`
# por historia: mismo import de modelo que ya hace `application/scope.py`.
from src.modules.users.infrastructure.models import Almacen
from src.shared import fechas


class OrdenProduccionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, orden_id: uuid.UUID) -> OrdenProduccion | None:
        return self.s.get(OrdenProduccion, orden_id)

    def get_by_idempotency(self, idempotency_key: str) -> OrdenProduccion | None:
        return self.s.scalar(
            select(OrdenProduccion).where(
                OrdenProduccion.idempotency_key == idempotency_key
            )
        )

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        almacen_id: uuid.UUID | None = None,
        estado: str | None = None,
    ):
        """La consulta sin ejecutar: el router la pagina (ADR-026).

        La orden no lleva empresa — la hereda de su almacén, igual que el
        `scope` del módulo (ADR-004).
        """
        q = select(OrdenProduccion)
        if almacen_id is not None:
            q = q.where(OrdenProduccion.almacen_id == almacen_id)
        if estado is not None:
            q = q.where(OrdenProduccion.estado == estado)
        if empresa_id is not None:
            q = q.join(Almacen, Almacen.id == OrdenProduccion.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return q.order_by(OrdenProduccion.created_at.desc())

    def add(self, orden: OrdenProduccion) -> OrdenProduccion:
        self.s.add(orden)
        self.s.flush()
        return orden

    def abierta_de(
        self, articulo_id: uuid.UUID, almacen_id: uuid.UUID
    ) -> OrdenProduccion | None:
        """Una orden del mismo artículo en ese almacén que todavía no cerró
        control de calidad (RN-PRD-007/011): el listener de necesidad no crea
        una segunda mientras la primera siga abierta."""
        return self.s.scalar(
            select(OrdenProduccion).where(
                OrdenProduccion.articulo_id == articulo_id,
                OrdenProduccion.almacen_id == almacen_id,
                OrdenProduccion.estado.in_(("borrador", "en_proceso")),
            )
        )

    def consumos(self, orden_id: uuid.UUID) -> list[ConsumoProduccionItem]:
        return list(
            self.s.scalars(
                select(ConsumoProduccionItem).where(
                    ConsumoProduccionItem.orden_produccion_id == orden_id
                )
            )
        )

    def trabajadores(self, orden_id: uuid.UUID) -> list[OrdenProduccionTrabajador]:
        return list(
            self.s.scalars(
                select(OrdenProduccionTrabajador).where(
                    OrdenProduccionTrabajador.orden_produccion_id == orden_id
                )
            )
        )

    def de_plan(self, plan_id: uuid.UUID) -> list[OrdenProduccion]:
        return list(
            self.s.scalars(
                select(OrdenProduccion).where(OrdenProduccion.plan_produccion_id == plan_id)
            )
        )

    def hijas_de(self, orden_id: uuid.UUID) -> list[OrdenProduccion]:
        return list(
            self.s.scalars(
                select(OrdenProduccion).where(OrdenProduccion.orden_padre_id == orden_id)
            )
        )

    def tiene_hija_pendiente(self, orden_id: uuid.UUID) -> bool:
        """RN-PRD-020: la orden padre no admite consumo mientras tenga una
        hija que no llegó a `conforme` — mismo patrón que
        `accounting.CuentaContableRepo.tiene_hijas`, existencia, no lista."""
        return (
            self.s.scalar(
                select(OrdenProduccion.id)
                .where(
                    OrdenProduccion.orden_padre_id == orden_id,
                    OrdenProduccion.estado != "conforme",
                )
                .limit(1)
            )
            is not None
        )

    def completadas_en_jornada(
        self, almacen_id: uuid.UUID, jornada
    ) -> list[OrdenProduccion]:
        """Las que cerraron control de calidad ese día de calendario del
        negocio (RN-DOC-010): son las únicas con costo/merma definitivos —
        una orden todavía `en_proceso` no tiene nada que consolidar."""
        return list(
            self.s.scalars(
                select(OrdenProduccion).where(
                    OrdenProduccion.almacen_id == almacen_id,
                    OrdenProduccion.completado_at >= fechas.inicio_dia_utc(jornada),
                    OrdenProduccion.completado_at <= fechas.fin_dia_utc(jornada),
                )
            )
        )


class PlanProduccionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, plan_id: uuid.UUID) -> PlanProduccion | None:
        return self.s.get(PlanProduccion, plan_id)

    def get_por_clave(
        self, almacen_id: uuid.UUID, fecha, turno: str, linea_produccion: str
    ) -> PlanProduccion | None:
        """RN-PRD-012: una línea, un tipo de receta por turno — la clave
        natural que reemplaza a una `idempotency_key` explícita."""
        return self.s.scalar(
            select(PlanProduccion).where(
                PlanProduccion.almacen_id == almacen_id,
                PlanProduccion.fecha == fecha,
                PlanProduccion.turno == turno,
                PlanProduccion.linea_produccion == linea_produccion,
            )
        )

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        almacen_id: uuid.UUID | None = None,
        fecha=None,
        estado: str | None = None,
    ):
        """La consulta sin ejecutar: el router la pagina (ADR-026)."""
        q = select(PlanProduccion)
        if almacen_id is not None:
            q = q.where(PlanProduccion.almacen_id == almacen_id)
        if fecha is not None:
            q = q.where(PlanProduccion.fecha == fecha)
        if estado is not None:
            q = q.where(PlanProduccion.estado == estado)
        if empresa_id is not None:
            q = q.join(Almacen, Almacen.id == PlanProduccion.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return q.order_by(PlanProduccion.fecha.desc(), PlanProduccion.created_at.desc())

    def add(self, plan: PlanProduccion) -> PlanProduccion:
        self.s.add(plan)
        self.s.flush()
        return plan


class ChecklistInocuidadTurnoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, checklist_id: uuid.UUID) -> ChecklistInocuidadTurno | None:
        return self.s.get(ChecklistInocuidadTurno, checklist_id)

    def get_por_clave(
        self, almacen_id: uuid.UUID, fecha, turno: str
    ) -> ChecklistInocuidadTurno | None:
        return self.s.scalar(
            select(ChecklistInocuidadTurno).where(
                ChecklistInocuidadTurno.almacen_id == almacen_id,
                ChecklistInocuidadTurno.fecha == fecha,
                ChecklistInocuidadTurno.turno == turno,
            )
        )

    def vigente_de(self, almacen_id: uuid.UUID, fecha) -> ChecklistInocuidadTurno | None:
        """El checklist más reciente del almacén para esa fecha, sin importar
        turno (`orden_produccion` no registra en cuál se creó): una vez
        bloqueada la cocina, sigue bloqueada hasta que un checklist nuevo la
        reapruebe."""
        return self.s.scalar(
            select(ChecklistInocuidadTurno)
            .where(
                ChecklistInocuidadTurno.almacen_id == almacen_id,
                ChecklistInocuidadTurno.fecha == fecha,
            )
            .order_by(ChecklistInocuidadTurno.created_at.desc())
            .limit(1)
        )

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        almacen_id: uuid.UUID | None = None,
        fecha=None,
        estado: str | None = None,
    ):
        """La consulta sin ejecutar: el router la pagina (ADR-026)."""
        q = select(ChecklistInocuidadTurno)
        if almacen_id is not None:
            q = q.where(ChecklistInocuidadTurno.almacen_id == almacen_id)
        if fecha is not None:
            q = q.where(ChecklistInocuidadTurno.fecha == fecha)
        if estado is not None:
            q = q.where(ChecklistInocuidadTurno.estado == estado)
        if empresa_id is not None:
            q = q.join(Almacen, Almacen.id == ChecklistInocuidadTurno.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return q.order_by(
            ChecklistInocuidadTurno.fecha.desc(), ChecklistInocuidadTurno.created_at.desc()
        )

    def add(self, checklist: ChecklistInocuidadTurno) -> ChecklistInocuidadTurno:
        self.s.add(checklist)
        self.s.flush()
        return checklist


class ReporteProduccionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, reporte_id: uuid.UUID) -> ReporteProduccion | None:
        return self.s.get(ReporteProduccion, reporte_id)

    def get_por_clave(self, almacen_id: uuid.UUID, jornada) -> ReporteProduccion | None:
        return self.s.scalar(
            select(ReporteProduccion).where(
                ReporteProduccion.almacen_id == almacen_id,
                ReporteProduccion.jornada == jornada,
            )
        )

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        almacen_id: uuid.UUID | None = None,
        jornada=None,
    ):
        """La consulta sin ejecutar: el router la pagina (ADR-026)."""
        q = select(ReporteProduccion)
        if almacen_id is not None:
            q = q.where(ReporteProduccion.almacen_id == almacen_id)
        if jornada is not None:
            q = q.where(ReporteProduccion.jornada == jornada)
        if empresa_id is not None:
            q = q.join(Almacen, Almacen.id == ReporteProduccion.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return q.order_by(ReporteProduccion.jornada.desc(), ReporteProduccion.created_at.desc())

    def add(self, reporte: ReporteProduccion) -> ReporteProduccion:
        self.s.add(reporte)
        self.s.flush()
        return reporte
