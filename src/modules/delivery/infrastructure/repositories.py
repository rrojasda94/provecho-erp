"""Repositorios SQLAlchemy del módulo delivery. La sesión es la Unit of Work."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.delivery.infrastructure.models import (
    Entrega,
    PosicionRepartidor,
    Repartidor,
    RutaReparto,
)

#: Estados de ruta que siguen "vivas" — el tablero las muestra, un
#: repartidor las ve en `GET /delivery/mi/rutas`.
RUTAS_VIVAS = ("planificada", "en_curso")


class RepartidorRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, repartidor_id: uuid.UUID) -> Repartidor | None:
        return self.s.get(Repartidor, repartidor_id)

    def get_por_usuario(self, usuario_id: uuid.UUID) -> Repartidor | None:
        return self.s.scalar(
            select(Repartidor).where(
                Repartidor.usuario_id == usuario_id, Repartidor.deleted_at.is_(None)
            )
        )

    def get_por_trabajador(self, trabajador_id: uuid.UUID) -> Repartidor | None:
        return self.s.scalar(
            select(Repartidor).where(
                Repartidor.trabajador_id == trabajador_id,
                Repartidor.deleted_at.is_(None),
            )
        )

    def q_list(
        self,
        sucursal_id: uuid.UUID | None = None,
        *,
        activo: bool | None = None,
    ):
        stmt = select(Repartidor).where(Repartidor.deleted_at.is_(None))
        if sucursal_id is not None:
            stmt = stmt.where(Repartidor.sucursal_id == sucursal_id)
        if activo is not None:
            stmt = stmt.where(Repartidor.activo == activo)
        return stmt.order_by(Repartidor.created_at)

    def list(
        self, sucursal_id: uuid.UUID | None = None, *, activo: bool | None = None
    ) -> list[Repartidor]:
        return list(self.s.scalars(self.q_list(sucursal_id, activo=activo)))

    def add(self, repartidor: Repartidor) -> Repartidor:
        self.s.add(repartidor)
        self.s.flush()
        return repartidor


class RutaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, ruta_id: uuid.UUID) -> RutaReparto | None:
        return self.s.get(RutaReparto, ruta_id)

    def add(self, ruta: RutaReparto) -> RutaReparto:
        self.s.add(ruta)
        self.s.flush()
        return ruta

    def q_list(
        self,
        sucursal_ids: Sequence[uuid.UUID] | None = None,
        *,
        estado: str | None = None,
        fecha: date | None = None,
    ):
        stmt = select(RutaReparto).order_by(RutaReparto.created_at.desc())
        if sucursal_ids:
            stmt = stmt.where(RutaReparto.sucursal_id.in_(list(sucursal_ids)))
        if estado is not None:
            stmt = stmt.where(RutaReparto.estado == estado)
        if fecha is not None:
            stmt = stmt.where(
                RutaReparto.created_at >= datetime(fecha.year, fecha.month, fecha.day),
            )
        return stmt

    def vivas_de_sucursales(self, sucursal_ids: Sequence[uuid.UUID]) -> list[RutaReparto]:
        """Rutas `planificada`/`en_curso` de estas sucursales — lo que
        muestra el tablero de despacho."""
        if not sucursal_ids:
            return []
        return list(
            self.s.scalars(
                select(RutaReparto)
                .where(
                    RutaReparto.sucursal_id.in_(list(sucursal_ids)),
                    RutaReparto.estado.in_(RUTAS_VIVAS),
                )
                .order_by(RutaReparto.created_at.desc())
            )
        )

    def vivas_de_repartidor(self, repartidor_id: uuid.UUID) -> list[RutaReparto]:
        """Rutas vivas de un repartidor — `GET /delivery/mi/rutas`."""
        return list(
            self.s.scalars(
                select(RutaReparto)
                .where(
                    RutaReparto.repartidor_id == repartidor_id,
                    RutaReparto.estado.in_(RUTAS_VIVAS),
                )
                .order_by(RutaReparto.created_at)
            )
        )


class EntregaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, entrega_id: uuid.UUID) -> Entrega | None:
        return self.s.get(Entrega, entrega_id)

    def get_por_venta(self, venta_id: uuid.UUID) -> Entrega | None:
        return self.s.scalar(select(Entrega).where(Entrega.venta_id == venta_id))

    def get_por_token(self, token: str) -> Entrega | None:
        return self.s.scalar(select(Entrega).where(Entrega.token_publico == token))

    def add(self, entrega: Entrega) -> Entrega:
        self.s.add(entrega)
        self.s.flush()
        return entrega

    def de_ruta(self, ruta_id: uuid.UUID) -> list[Entrega]:
        return list(
            self.s.scalars(
                select(Entrega).where(Entrega.ruta_id == ruta_id).order_by(Entrega.orden_parada)
            )
        )

    def venta_ids_con_entrega_abierta(self, venta_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        """De estas ventas, cuáles ya tienen una `entrega` que no sea
        `cancelada` — el tablero las resta de "listos sin asignar" aunque
        el evento `sales.pedido_listo` nunca haya llegado (ADR-098, la
        consulta manda, no el evento)."""
        if not venta_ids:
            return set()
        filas = self.s.scalars(
            select(Entrega.venta_id).where(
                Entrega.venta_id.in_(list(venta_ids)),
                Entrega.estado != "cancelada",
            )
        )
        return set(filas)

    def q_historial(
        self,
        sucursal_ids: Sequence[uuid.UUID] | None = None,
        *,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        estado: str | None = None,
        repartidor_id: uuid.UUID | None = None,
    ):
        stmt = select(Entrega).order_by(Entrega.created_at.desc())
        if sucursal_ids:
            stmt = stmt.where(Entrega.sucursal_id.in_(list(sucursal_ids)))
        if desde is not None:
            stmt = stmt.where(Entrega.created_at >= desde)
        if hasta is not None:
            stmt = stmt.where(Entrega.created_at <= hasta)
        if estado is not None:
            stmt = stmt.where(Entrega.estado == estado)
        if repartidor_id is not None:
            stmt = stmt.where(Entrega.repartidor_id == repartidor_id)
        return stmt


class PosicionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, posicion: PosicionRepartidor) -> PosicionRepartidor:
        self.s.add(posicion)
        self.s.flush()
        return posicion

    def anteriores_a(self, limite: datetime) -> list[PosicionRepartidor]:
        """Breadcrumb más viejo que `limite` — lo usa el barrido de purga
        (`delivery_posiciones_retencion_dias`)."""
        return list(
            self.s.scalars(
                select(PosicionRepartidor).where(PosicionRepartidor.registrado_at < limite)
            )
        )
