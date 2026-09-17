"""Repositorios SQLAlchemy del módulo supervision. La sesión es la Unit of Work."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.supervision.infrastructure.models import (
    CategoriaTarea,
    InformeDiario,
    TareaInstancia,
    TareaPlantilla,
)


class CategoriaTareaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, categoria_id: uuid.UUID) -> CategoriaTarea | None:
        return self.s.get(CategoriaTarea, categoria_id)

    def q_list(self, empresa_id: uuid.UUID | None = None):
        q = select(CategoriaTarea)
        if empresa_id is not None:
            q = q.where(CategoriaTarea.empresa_id == empresa_id)
        return q.order_by(CategoriaTarea.nombre)

    def add(self, categoria: CategoriaTarea) -> CategoriaTarea:
        self.s.add(categoria)
        self.s.flush()
        return categoria


class TareaPlantillaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, plantilla_id: uuid.UUID) -> TareaPlantilla | None:
        return self.s.get(TareaPlantilla, plantilla_id)

    def q_list(self, empresa_id: uuid.UUID | None = None):
        q = select(TareaPlantilla)
        if empresa_id is not None:
            q = q.where(TareaPlantilla.empresa_id == empresa_id)
        return q.order_by(TareaPlantilla.momento, TareaPlantilla.orden)

    def activas_de_sucursal(
        self, sucursal_id: uuid.UUID, marca_id: uuid.UUID
    ) -> list[TareaPlantilla]:
        """Las plantillas que aplican a esta sucursal: propias o de su
        marca (`sucursal_id IS NULL`)."""
        return list(
            self.s.scalars(
                select(TareaPlantilla).where(
                    TareaPlantilla.activa.is_(True),
                    (TareaPlantilla.sucursal_id == sucursal_id)
                    | (
                        (TareaPlantilla.sucursal_id.is_(None))
                        & (TareaPlantilla.marca_id == marca_id)
                    ),
                )
            )
        )

    def add(self, plantilla: TareaPlantilla) -> TareaPlantilla:
        self.s.add(plantilla)
        self.s.flush()
        return plantilla


class TareaInstanciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, instancia_id: uuid.UUID) -> TareaInstancia | None:
        return self.s.get(TareaInstancia, instancia_id)

    def existe_de_plantilla(
        self, plantilla_id: uuid.UUID, sucursal_id: uuid.UUID, fecha: date
    ) -> bool:
        return (
            self.s.scalar(
                select(TareaInstancia.id).where(
                    TareaInstancia.plantilla_id == plantilla_id,
                    TareaInstancia.sucursal_id == sucursal_id,
                    TareaInstancia.fecha == fecha,
                )
            )
            is not None
        )

    def q_de_sucursal(self, sucursal_id: uuid.UUID, fecha: date):
        return (
            select(TareaInstancia)
            .where(TareaInstancia.sucursal_id == sucursal_id, TareaInstancia.fecha == fecha)
            .order_by(TareaInstancia.momento, TareaInstancia.orden)
        )

    def q_asignadas_a(self, usuario_id: uuid.UUID, fecha: date):
        return (
            select(TareaInstancia)
            .where(TareaInstancia.asignado_a == usuario_id, TareaInstancia.fecha == fecha)
            .order_by(TareaInstancia.momento, TareaInstancia.orden)
        )

    def pendientes_de_sucursal(self, sucursal_id: uuid.UUID, fecha: date) -> list[TareaInstancia]:
        return list(
            self.s.scalars(
                select(TareaInstancia).where(
                    TareaInstancia.sucursal_id == sucursal_id,
                    TareaInstancia.fecha == fecha,
                    TareaInstancia.estado == "pendiente",
                )
            )
        )

    def de_sucursal(self, sucursal_id: uuid.UUID, fecha: date) -> list[TareaInstancia]:
        return list(self.s.scalars(self.q_de_sucursal(sucursal_id, fecha)))

    def add(self, instancia: TareaInstancia) -> TareaInstancia:
        self.s.add(instancia)
        self.s.flush()
        return instancia


class InformeDiarioRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, informe_id: uuid.UUID) -> InformeDiario | None:
        return self.s.get(InformeDiario, informe_id)

    def get_de(self, sucursal_id: uuid.UUID, fecha: date) -> InformeDiario | None:
        return self.s.scalar(
            select(InformeDiario).where(
                InformeDiario.sucursal_id == sucursal_id, InformeDiario.fecha == fecha
            )
        )

    def q_list(self, sucursal_id: uuid.UUID | None = None):
        q = select(InformeDiario)
        if sucursal_id is not None:
            q = q.where(InformeDiario.sucursal_id == sucursal_id)
        return q.order_by(InformeDiario.fecha.desc())

    def add(self, informe: InformeDiario) -> InformeDiario:
        self.s.add(informe)
        self.s.flush()
        return informe
