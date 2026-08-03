"""Casos de uso de catálogo: CRUD de categorías, artículos y SKUs."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.inventory.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Sku,
    UnidadMedida,
)
from src.modules.inventory.infrastructure.repositories import (
    ArticuloRepo,
    CategoriaRepo,
    CategoriaUdmRepo,
    SkuRepo,
    UnidadMedidaRepo,
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
    frecuencia_conteo: str | None = None,
) -> Categoria:
    _validar_frecuencia(frecuencia_conteo)
    repo = CategoriaRepo(session)
    if repo.get_by_nombre(empresa_id, nombre):
        raise Conflicto(f"categoría '{nombre}' ya existe en la empresa")
    return repo.add(
        Categoria(
            empresa_id=empresa_id,
            nombre=nombre,
            asiento_contable_config=asiento_contable_config,
            frecuencia_conteo=frecuencia_conteo,
        )
    )


def _validar_frecuencia(frecuencia: str | None) -> None:
    if frecuencia is not None and frecuencia not in rules.FRECUENCIAS_CONTEO:
        raise ReglaNegocio(f"frecuencia de conteo inválida: {frecuencia}")


def editar_categoria(
    session: Session,
    categoria_id: uuid.UUID,
    *,
    nombre: str | None = None,
    asiento_contable_config: dict | None = None,
    frecuencia_conteo: str | None = None,
    quitar_frecuencia: bool = False,
) -> Categoria:
    """`quitar_frecuencia` saca la categoría del conteo cíclico: sin ese
    flag explícito, `frecuencia_conteo=None` significa "no la toques" y no
    habría forma de volver a NULL."""
    _validar_frecuencia(frecuencia_conteo)
    categoria = CategoriaRepo(session).get(categoria_id)
    if categoria is None:
        raise NoEncontrado("categoría no encontrada")
    if nombre is not None:
        categoria.nombre = nombre
    if asiento_contable_config is not None:
        categoria.asiento_contable_config = asiento_contable_config
    if quitar_frecuencia:
        categoria.frecuencia_conteo = None
    elif frecuencia_conteo is not None:
        categoria.frecuencia_conteo = frecuencia_conteo
    return categoria


def listar_categorias(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[Categoria]:
    return CategoriaRepo(session).list(empresa_id)


def listar_unidades_medida(session: Session) -> list[UnidadMedida]:
    return UnidadMedidaRepo(session).list()


def crear_categoria_udm(session: Session, *, nombre: str) -> CategoriaUdm:
    repo = CategoriaUdmRepo(session)
    if repo.get_by_nombre(nombre) is not None:
        raise Conflicto(f"la categoría de unidad de medida '{nombre}' ya existe")
    return repo.add(CategoriaUdm(nombre=nombre))


def listar_categorias_udm(session: Session) -> list[CategoriaUdm]:
    return CategoriaUdmRepo(session).list()


def crear_unidad_medida(
    session: Session,
    *,
    categoria_udm_id: uuid.UUID,
    nombre: str,
    ratio: Decimal,
    decimales: int,
) -> UnidadMedida:
    _existe(session, CategoriaUdm, categoria_udm_id, "categoría de unidad de medida")
    repo = UnidadMedidaRepo(session)
    if repo.get_by_nombre(categoria_udm_id, nombre) is not None:
        raise Conflicto(f"'{nombre}' ya existe en esa categoría de UdM")
    return repo.add(
        UnidadMedida(
            categoria_udm_id=categoria_udm_id,
            nombre=nombre,
            ratio=ratio,
            decimales=decimales,
        )
    )


def editar_unidad_medida(session: Session, unidad_medida_id: uuid.UUID, **campos) -> UnidadMedida:
    unidad = UnidadMedidaRepo(session).get(unidad_medida_id)
    if unidad is None:
        raise NoEncontrado("unidad de medida no encontrada")
    for campo in ("nombre", "ratio", "decimales"):
        if campo in campos and campos[campo] is not None:
            setattr(unidad, campo, campos[campo])
    return unidad


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
    controla_lote: bool = False,
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
            controla_lote=controla_lote,
        )
    )


def editar_articulo(session: Session, articulo_id: uuid.UUID, **campos) -> Articulo:
    articulo = ArticuloRepo(session).get(articulo_id)
    if articulo is None:
        raise NoEncontrado("artículo no encontrado")
    for campo in (
        "nombre", "categoria_id", "tipo", "costo_promedio", "archivado", "controla_lote",
    ):
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
