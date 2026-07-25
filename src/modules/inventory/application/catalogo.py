"""Casos de uso de catálogo: CRUD de categorías, artículos y SKUs."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.inventory.application.errors import Conflicto, NoEncontrado
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    Sku,
    UnidadMedida,
)
from src.modules.inventory.infrastructure.repositories import (
    ArticuloRepo,
    CategoriaRepo,
    SkuRepo,
)


def _existe(session: Session, model, entidad_id, nombre: str) -> None:
    if entidad_id is not None and session.get(model, entidad_id) is None:
        raise NoEncontrado(f"{nombre} no encontrado")


def crear_categoria(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombre: str,
    asiento_contable_config: dict | None = None,
) -> Categoria:
    repo = CategoriaRepo(session)
    if repo.get_by_nombre(empresa_id, nombre):
        raise Conflicto(f"categoría '{nombre}' ya existe en la empresa")
    return repo.add(
        Categoria(
            empresa_id=empresa_id,
            nombre=nombre,
            asiento_contable_config=asiento_contable_config,
        )
    )


def listar_categorias(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[Categoria]:
    return CategoriaRepo(session).list(empresa_id)


def crear_articulo(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    id_interno: str,
    nombre: str,
    unidad_medida_id: uuid.UUID,
    tipo: str,
    categoria_id: uuid.UUID | None = None,
    costo_promedio: Decimal = Decimal(0),
) -> Articulo:
    _existe(session, UnidadMedida, unidad_medida_id, "unidad de medida")
    _existe(session, Categoria, categoria_id, "categoría")
    repo = ArticuloRepo(session)
    if repo.get_by_id_interno(id_interno):
        raise Conflicto(f"id_interno '{id_interno}' ya existe")
    return repo.add(
        Articulo(
            empresa_id=empresa_id,
            id_interno=id_interno,
            nombre=nombre,
            unidad_medida_id=unidad_medida_id,
            tipo=tipo,
            categoria_id=categoria_id,
            costo_promedio=costo_promedio,
        )
    )


def editar_articulo(session: Session, articulo_id: uuid.UUID, **campos) -> Articulo:
    articulo = ArticuloRepo(session).get(articulo_id)
    if articulo is None:
        raise NoEncontrado("artículo no encontrado")
    for campo in ("nombre", "categoria_id", "tipo", "costo_promedio", "archivado"):
        if campo in campos and campos[campo] is not None:
            setattr(articulo, campo, campos[campo])
    return articulo


def listar_articulos(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[Articulo]:
    return ArticuloRepo(session).list(empresa_id)


def crear_sku(
    session: Session,
    *,
    articulo_id: uuid.UUID,
    codigo: str,
    codigo_barras: str | None = None,
) -> Sku:
    if ArticuloRepo(session).get(articulo_id) is None:
        raise NoEncontrado("artículo no encontrado")
    repo = SkuRepo(session)
    if repo.get_by_codigo(codigo):
        raise Conflicto(f"código de SKU '{codigo}' ya existe")
    return repo.add(
        Sku(articulo_id=articulo_id, codigo=codigo, codigo_barras=codigo_barras)
    )
