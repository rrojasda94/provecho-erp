"""Repositorios SQLAlchemy del módulo inventory. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.infrastructure.models import (
    Ajuste,
    Articulo,
    Categoria,
    Lote,
    MovimientoInventario,
    Sku,
    Stock,
    StockLote,
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
