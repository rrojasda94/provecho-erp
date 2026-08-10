"""Repositorios del módulo. La sesión es la Unit of Work: acá se hace
`flush()` y nunca `commit()` — eso es del router (o del listener, que abre
la suya)."""

# Los métodos `list()` tapan al `list` builtin para toda anotación que venga
# después en la misma clase. Mismo motivo y misma solución que en
# `accounting/infrastructure/repositories.py`.
from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.modules.reports.domain import escalamiento
from src.modules.reports.infrastructure.models import (
    Area,
    AreaMiembro,
    EntregaReporte,
    ReglaDestinatario,
    ReglaDistribucion,
    ReporteEmitido,
    ReporteEscalamiento,
)


class AreaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, area_id: uuid.UUID) -> Area | None:
        return self.s.get(Area, area_id)

    def por_codigo(self, empresa_id: uuid.UUID, codigo: str) -> Area | None:
        return self.s.scalar(
            select(Area).where(Area.empresa_id == empresa_id, Area.codigo == codigo)
        )

    def q_list(self, empresa_id: uuid.UUID | None = None) -> Select:
        q = select(Area)
        if empresa_id is not None:
            q = q.where(Area.empresa_id == empresa_id)
        return q.order_by(Area.nombre)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Area]:
        return list(self.s.scalars(self.q_list(empresa_id)))

    def miembros(self, area_id: uuid.UUID) -> list[AreaMiembro]:
        return list(
            self.s.scalars(select(AreaMiembro).where(AreaMiembro.area_id == area_id))
        )

    def miembro(self, miembro_id: uuid.UUID) -> AreaMiembro | None:
        return self.s.get(AreaMiembro, miembro_id)

    def add(self, area: Area) -> Area:
        self.s.add(area)
        self.s.flush()
        return area

    def add_miembro(self, miembro: AreaMiembro) -> AreaMiembro:
        self.s.add(miembro)
        self.s.flush()
        return miembro


class ReglaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, regla_id: uuid.UUID) -> ReglaDistribucion | None:
        return self.s.get(ReglaDistribucion, regla_id)

    def q_list(
        self, empresa_id: uuid.UUID | None = None, codigo_emision: str | None = None
    ) -> Select:
        q = select(ReglaDistribucion)
        if empresa_id is not None:
            q = q.where(ReglaDistribucion.empresa_id == empresa_id)
        if codigo_emision is not None:
            q = q.where(ReglaDistribucion.codigo_emision == codigo_emision)
        return q.order_by(ReglaDistribucion.codigo_emision)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[ReglaDistribucion]:
        return list(self.s.scalars(self.q_list(empresa_id)))

    def activas_de(
        self, empresa_id: uuid.UUID, codigo_emision: str
    ) -> list[ReglaDistribucion]:
        """Las candidatas de una emisión: `domain.rules.elegir_regla` decide
        cuál gana entre la de la sucursal y la general."""
        return list(
            self.s.scalars(
                select(ReglaDistribucion).where(
                    ReglaDistribucion.empresa_id == empresa_id,
                    ReglaDistribucion.codigo_emision == codigo_emision,
                    ReglaDistribucion.activa.is_(True),
                )
            )
        )

    def destinatarios(self, regla_id: uuid.UUID) -> list[ReglaDestinatario]:
        return list(
            self.s.scalars(
                select(ReglaDestinatario).where(ReglaDestinatario.regla_id == regla_id)
            )
        )

    def destinatarios_de(
        self, regla_ids: list[uuid.UUID]
    ) -> list[ReglaDestinatario]:
        """Los de varias reglas en una consulta: la matriz los pide todos y
        hacerlo en bucle es una consulta por fila de la pantalla."""
        if not regla_ids:
            return []
        return list(
            self.s.scalars(
                select(ReglaDestinatario).where(ReglaDestinatario.regla_id.in_(regla_ids))
            )
        )

    def add(self, regla: ReglaDistribucion) -> ReglaDistribucion:
        self.s.add(regla)
        self.s.flush()
        return regla

    def add_destinatario(self, destinatario: ReglaDestinatario) -> ReglaDestinatario:
        self.s.add(destinatario)
        self.s.flush()
        return destinatario


class ReporteEmitidoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, reporte_id: uuid.UUID) -> ReporteEmitido | None:
        return self.s.get(ReporteEmitido, reporte_id)

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        *,
        codigo_emision: str | None = None,
        sucursal_ids: list[uuid.UUID] | None = None,
    ) -> Select:
        q = select(ReporteEmitido)
        if empresa_id is not None:
            q = q.where(ReporteEmitido.empresa_id == empresa_id)
        if codigo_emision is not None:
            q = q.where(ReporteEmitido.codigo_emision == codigo_emision)
        if sucursal_ids:
            q = q.where(ReporteEmitido.sucursal_id.in_(sucursal_ids))
        return q.order_by(ReporteEmitido.emitido_at.desc())

    def q_mios(self, usuario_id: uuid.UUID) -> Select:
        """Lo que me fue entregado. Join a `entrega_reporte` en vez de dos
        consultas: la bandeja se pinta en cada carga de pantalla."""
        return (
            select(ReporteEmitido)
            .join(
                EntregaReporte,
                EntregaReporte.reporte_emitido_id == ReporteEmitido.id,
            )
            .where(EntregaReporte.usuario_id == usuario_id)
            .order_by(ReporteEmitido.emitido_at.desc())
        )

    def entregas(self, reporte_id: uuid.UUID) -> list[EntregaReporte]:
        return list(
            self.s.scalars(
                select(EntregaReporte).where(
                    EntregaReporte.reporte_emitido_id == reporte_id
                )
            )
        )

    def es_destinatario(self, reporte_id: uuid.UUID, usuario_id: uuid.UUID) -> bool:
        return (
            self.s.scalar(
                select(EntregaReporte.id).where(
                    EntregaReporte.reporte_emitido_id == reporte_id,
                    EntregaReporte.usuario_id == usuario_id,
                )
            )
            is not None
        )

    def add(self, reporte: ReporteEmitido) -> ReporteEmitido:
        self.s.add(reporte)
        self.s.flush()
        return reporte

    def add_entrega(self, entrega: EntregaReporte) -> EntregaReporte:
        self.s.add(entrega)
        self.s.flush()
        return entrega


class EscalamientoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, escalamiento_id: uuid.UUID) -> ReporteEscalamiento | None:
        return self.s.get(ReporteEscalamiento, escalamiento_id)

    def abierto_de(self, reporte_id: uuid.UUID) -> ReporteEscalamiento | None:
        """La cadena viva de ese reporte. Lo respalda el índice parcial
        `uq_escalamiento_abierto_por_reporte`; esto lo detecta antes para
        devolver un 409 con mensaje en vez de un error de integridad."""
        return self.s.scalar(
            select(ReporteEscalamiento).where(
                ReporteEscalamiento.reporte_emitido_id == reporte_id,
                ReporteEscalamiento.estado.not_in(escalamiento.ESTADOS_TERMINADOS),
            )
        )

    def de_reporte(self, reporte_id: uuid.UUID) -> list[ReporteEscalamiento]:
        return list(
            self.s.scalars(
                select(ReporteEscalamiento)
                .where(ReporteEscalamiento.reporte_emitido_id == reporte_id)
                .order_by(ReporteEscalamiento.created_at.desc())
            )
        )

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        *,
        estado: str | None = None,
        nivel_actual: str | None = None,
        motivo: str | None = None,
        origen: str | None = None,
    ) -> Select:
        q = select(ReporteEscalamiento)
        if empresa_id is not None:
            q = q.where(ReporteEscalamiento.empresa_id == empresa_id)
        if estado is not None:
            q = q.where(ReporteEscalamiento.estado == estado)
        if nivel_actual is not None:
            q = q.where(ReporteEscalamiento.nivel_actual == nivel_actual)
        if motivo is not None:
            q = q.where(ReporteEscalamiento.motivo == motivo)
        if origen is not None:
            q = q.where(ReporteEscalamiento.origen == origen)
        return q.order_by(ReporteEscalamiento.created_at.desc())

    def add(self, fila: ReporteEscalamiento) -> ReporteEscalamiento:
        self.s.add(fila)
        self.s.flush()
        return fila
