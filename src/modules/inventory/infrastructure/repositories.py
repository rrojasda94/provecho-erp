"""Repositorios SQLAlchemy del módulo inventory. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.modules.inventory.infrastructure.models import (
    Ajuste,
    Articulo,
    Categoria,
    Conteo,
    ConteoItem,
    Lote,
    MovimientoInventario,
    ReservaStock,
    Sku,
    SolicitudInsumos,
    SolicitudItem,
    Stock,
    StockLote,
    Transferencia,
    TransferenciaItem,
    UnidadMedida,
)
from src.modules.users.infrastructure.models import Almacen


class ArticuloRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, articulo_id: uuid.UUID) -> Articulo | None:
        return self.s.get(Articulo, articulo_id)

    def get_by_id_interno(self, id_interno: str) -> Articulo | None:
        return self.s.scalar(select(Articulo).where(Articulo.id_interno == id_interno))

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Articulo]:
        q = select(Articulo).where(Articulo.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Articulo.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(Articulo.nombre)))

    def add(self, articulo: Articulo) -> Articulo:
        self.s.add(articulo)
        self.s.flush()
        return articulo


class CategoriaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, categoria_id: uuid.UUID) -> Categoria | None:
        return self.s.get(Categoria, categoria_id)

    def get_by_nombre(self, empresa_id: uuid.UUID, nombre: str) -> Categoria | None:
        return self.s.scalar(
            select(Categoria).where(
                Categoria.empresa_id == empresa_id, Categoria.nombre == nombre
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Categoria]:
        q = select(Categoria).where(Categoria.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Categoria.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(Categoria.nombre)))

    def add(self, categoria: Categoria) -> Categoria:
        self.s.add(categoria)
        self.s.flush()
        return categoria


class UnidadMedidaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def list(self) -> list[UnidadMedida]:
        # Global: sin filtro de empresa (RN-GER-010, docstring del modelo).
        return list(self.s.scalars(select(UnidadMedida).order_by(UnidadMedida.nombre)))


class SkuRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, sku_id: uuid.UUID) -> Sku | None:
        return self.s.get(Sku, sku_id)

    def get_by_codigo(self, codigo: str) -> Sku | None:
        return self.s.scalar(select(Sku).where(Sku.codigo == codigo))

    def add(self, sku: Sku) -> Sku:
        self.s.add(sku)
        self.s.flush()
        return sku


class StockRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(
        self, almacen_id: uuid.UUID, sku_id: uuid.UUID, for_update: bool = False
    ) -> Stock | None:
        q = select(Stock).where(
            Stock.almacen_id == almacen_id, Stock.sku_id == sku_id
        )
        if for_update:
            # Bloqueo de fila para evitar lost-update en movimientos
            # concurrentes (no-op en SQLite; efectivo en Postgres).
            q = q.with_for_update()
        return self.s.scalar(q)

    def list(
        self,
        almacen_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> list[Stock]:
        q = select(Stock)
        if almacen_id is not None:
            q = q.where(Stock.almacen_id == almacen_id)
        if empresa_id is not None:
            # El stock no lleva empresa: la hereda del almacén (ADR-004).
            q = q.join(Almacen, Almacen.id == Stock.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return list(self.s.scalars(q))

    def add(self, stock: Stock) -> Stock:
        self.s.add(stock)
        self.s.flush()
        return stock


class MovimientoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, mov: MovimientoInventario) -> MovimientoInventario:
        self.s.add(mov)
        self.s.flush()
        return mov

    def list(self, almacen_id: uuid.UUID, sku_id: uuid.UUID) -> list[MovimientoInventario]:
        return list(
            self.s.scalars(
                select(MovimientoInventario)
                .where(
                    MovimientoInventario.almacen_id == almacen_id,
                    MovimientoInventario.sku_id == sku_id,
                )
                .order_by(MovimientoInventario.ts)
            )
        )


class LoteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, lote_id: uuid.UUID) -> Lote | None:
        return self.s.get(Lote, lote_id)

    def get_by_codigo(self, articulo_id: uuid.UUID, codigo: str) -> Lote | None:
        return self.s.scalar(
            select(Lote).where(Lote.articulo_id == articulo_id, Lote.codigo == codigo)
        )

    def add(self, lote: Lote) -> Lote:
        self.s.add(lote)
        self.s.flush()
        return lote


class StockLoteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(
        self,
        almacen_id: uuid.UUID,
        sku_id: uuid.UUID,
        lote_id: uuid.UUID,
        for_update: bool = False,
    ) -> StockLote | None:
        q = select(StockLote).where(
            StockLote.almacen_id == almacen_id,
            StockLote.sku_id == sku_id,
            StockLote.lote_id == lote_id,
        )
        if for_update:
            q = q.with_for_update()
        return self.s.scalar(q)

    def fefo(self, almacen_id: uuid.UUID, sku_id: uuid.UUID) -> list[StockLote]:
        """Lotes con saldo, ordenados por vencimiento más próximo; los que no
        vencen van al final y entre ellos manda el más antiguo (FIFO)."""
        return list(
            self.s.scalars(
                select(StockLote)
                .join(Lote, Lote.id == StockLote.lote_id)
                .where(
                    StockLote.almacen_id == almacen_id,
                    StockLote.sku_id == sku_id,
                    StockLote.cantidad > 0,
                )
                .order_by(
                    Lote.fecha_vencimiento.is_(None),
                    Lote.fecha_vencimiento,
                    Lote.created_at,
                )
            )
        )

    def list(
        self,
        almacen_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> list[tuple[StockLote, Lote]]:
        q = select(StockLote, Lote).join(Lote, Lote.id == StockLote.lote_id)
        if almacen_id is not None:
            q = q.where(StockLote.almacen_id == almacen_id)
        if sku_id is not None:
            q = q.where(StockLote.sku_id == sku_id)
        if empresa_id is not None:
            # El stock no lleva empresa: la hereda del almacén (ADR-004).
            q = q.join(Almacen, Almacen.id == StockLote.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return [
            (sl, lote)
            for sl, lote in self.s.execute(
                q.order_by(
                    Lote.fecha_vencimiento.is_(None), Lote.fecha_vencimiento
                )
            )
        ]

    def add(self, stock_lote: StockLote) -> StockLote:
        self.s.add(stock_lote)
        self.s.flush()
        return stock_lote


class AjusteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, ajuste_id: uuid.UUID) -> Ajuste | None:
        return self.s.get(Ajuste, ajuste_id)

    def add(self, ajuste: Ajuste) -> Ajuste:
        self.s.add(ajuste)
        self.s.flush()
        return ajuste


class ReservaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, reserva_id: uuid.UUID) -> ReservaStock | None:
        return self.s.get(ReservaStock, reserva_id)

    def activas(
        self,
        almacen_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> list[ReservaStock]:
        q = select(ReservaStock).where(ReservaStock.estado == "activa")
        if almacen_id is not None:
            q = q.where(ReservaStock.almacen_id == almacen_id)
        if sku_id is not None:
            q = q.where(ReservaStock.sku_id == sku_id)
        if empresa_id is not None:
            # La reserva no lleva empresa: la hereda del almacén (ADR-004).
            q = q.join(Almacen, Almacen.id == ReservaStock.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return list(self.s.scalars(q))

    def por_referencia(self, referencia_id: uuid.UUID) -> list[ReservaStock]:
        return list(
            self.s.scalars(
                select(ReservaStock).where(
                    ReservaStock.referencia_id == referencia_id,
                    ReservaStock.estado == "activa",
                )
            )
        )

    def add(self, reserva: ReservaStock) -> ReservaStock:
        self.s.add(reserva)
        self.s.flush()
        return reserva


class SolicitudRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, solicitud_id: uuid.UUID) -> SolicitudInsumos | None:
        return self.s.get(SolicitudInsumos, solicitud_id)

    def items(self, solicitud_id: uuid.UUID) -> list[SolicitudItem]:
        return list(
            self.s.scalars(
                select(SolicitudItem).where(SolicitudItem.solicitud_id == solicitud_id)
            )
        )

    def add(self, solicitud: SolicitudInsumos) -> SolicitudInsumos:
        self.s.add(solicitud)
        self.s.flush()
        return solicitud

    def add_item(self, item: SolicitudItem) -> SolicitudItem:
        self.s.add(item)
        self.s.flush()
        return item

    # `list` va al final: nombrar así un método sombrea al builtin dentro
    # del cuerpo de la clase, y cualquier anotación `list[...]` que venga
    # después reventaría al evaluarse.
    def list(
        self,
        almacen_solicitante_id: uuid.UUID | None = None,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> "list[SolicitudInsumos]":
        q = select(SolicitudInsumos)
        if almacen_solicitante_id is not None:
            q = q.where(
                SolicitudInsumos.almacen_solicitante_id == almacen_solicitante_id
            )
        if estado is not None:
            q = q.where(SolicitudInsumos.estado == estado)
        if empresa_id is not None:
            q = q.join(
                Almacen, Almacen.id == SolicitudInsumos.almacen_solicitante_id
            ).where(Almacen.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(SolicitudInsumos.created_at.desc())))


class TransferenciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, transferencia_id: uuid.UUID) -> Transferencia | None:
        return self.s.get(Transferencia, transferencia_id)

    def items(self, transferencia_id: uuid.UUID) -> list[TransferenciaItem]:
        return list(
            self.s.scalars(
                select(TransferenciaItem).where(
                    TransferenciaItem.transferencia_id == transferencia_id
                )
            )
        )

    def add(self, transferencia: Transferencia) -> Transferencia:
        self.s.add(transferencia)
        self.s.flush()
        return transferencia

    def add_item(self, item: TransferenciaItem) -> TransferenciaItem:
        self.s.add(item)
        self.s.flush()
        return item

    # Ver la nota de `SolicitudRepo.list`: este método sombrea al builtin.
    def list(
        self,
        almacen_id: uuid.UUID | None = None,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> "list[Transferencia]":
        """`almacen_id` matchea origen o destino: quien mira un almacén
        quiere ver lo que sale y lo que le llega."""
        q = select(Transferencia)
        if almacen_id is not None:
            q = q.where(
                or_(
                    Transferencia.origen_almacen_id == almacen_id,
                    Transferencia.destino_almacen_id == almacen_id,
                )
            )
        if estado is not None:
            q = q.where(Transferencia.estado == estado)
        if empresa_id is not None:
            q = q.join(
                Almacen, Almacen.id == Transferencia.origen_almacen_id
            ).where(Almacen.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(Transferencia.created_at.desc())))


class ConteoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, conteo_id: uuid.UUID) -> Conteo | None:
        return self.s.get(Conteo, conteo_id)

    def abierto_en(
        self, almacen_id: uuid.UUID, categoria_id: uuid.UUID | None
    ) -> Conteo | None:
        """Conteo abierto que ya cubre esa categoría en ese almacén.

        Un conteo general abierto (categoria_id NULL) bloquea a todos: ya
        los está contando. Y abrir uno general con cualquier conteo abierto
        encima también choca — por eso el filtro se relaja a "cualquiera".
        """
        q = select(Conteo).where(
            Conteo.almacen_id == almacen_id, Conteo.estado == "abierto"
        )
        if categoria_id is not None:
            q = q.where(
                or_(
                    Conteo.categoria_id == categoria_id,
                    Conteo.categoria_id.is_(None),
                )
            )
        return self.s.scalars(q).first()

    def ultimo_cerrado(
        self, almacen_id: uuid.UUID, categoria_id: uuid.UUID
    ) -> Conteo | None:
        """Último conteo cerrado que cubrió esa categoría — el general
        (categoria_id NULL) también cuenta: contó todo el almacén."""
        return self.s.scalars(
            select(Conteo)
            .where(
                Conteo.almacen_id == almacen_id,
                Conteo.estado == "cerrado",
                or_(
                    Conteo.categoria_id == categoria_id,
                    Conteo.categoria_id.is_(None),
                ),
            )
            .order_by(Conteo.cerrado_at.desc())
        ).first()

    def items(self, conteo_id: uuid.UUID) -> list[ConteoItem]:
        return list(
            self.s.scalars(
                select(ConteoItem).where(ConteoItem.conteo_id == conteo_id)
            )
        )

    def item(self, conteo_id: uuid.UUID, sku_id: uuid.UUID) -> ConteoItem | None:
        return self.s.scalar(
            select(ConteoItem).where(
                ConteoItem.conteo_id == conteo_id, ConteoItem.sku_id == sku_id
            )
        )

    def add(self, conteo: Conteo) -> Conteo:
        self.s.add(conteo)
        self.s.flush()
        return conteo

    def add_item(self, item: ConteoItem) -> ConteoItem:
        self.s.add(item)
        self.s.flush()
        return item
