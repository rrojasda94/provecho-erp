"""Casos de uso de catálogo comercial: productos vendibles y medios de pago."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.sales.application.errors import Conflicto, NoEncontrado
from src.modules.sales.infrastructure.models import MedioPago, ProductoComercial
from src.modules.sales.infrastructure.repositories import (
    MedioPagoRepo,
    ProductoComercialRepo,
)


def crear_producto(
    session: Session,
    *,
    id_interno: str,
    marca_id: uuid.UUID,
    nombre: str,
    receta_id: uuid.UUID,
    empaque_id: uuid.UUID | None = None,
    modalidades_empaque: list | None = None,
    es_extra: bool = False,
) -> ProductoComercial:
    repo = ProductoComercialRepo(session)
    if repo.get_by_id_interno(id_interno):
        raise Conflicto(f"id_interno '{id_interno}' ya existe")
    return repo.add(
        ProductoComercial(
            id_interno=id_interno,
            marca_id=marca_id,
            nombre=nombre,
            receta_id=receta_id,
            empaque_id=empaque_id,
            modalidades_empaque=modalidades_empaque,
            es_extra=es_extra,
        )
    )


def vincular_extra(
    session: Session,
    *,
    producto_id: uuid.UUID,
    extra_id: uuid.UUID,
    maximo: int | None = None,
):
    """Habilita un extra sobre un producto (RN-COM-021).

    Se valida acá y no en el esquema porque las dos puntas son la misma
    tabla: nada a nivel de FK impide colgar una pizza de otra pizza.
    """
    repo = ProductoComercialRepo(session)
    producto = repo.get(producto_id)
    extra = repo.get(extra_id)
    if producto is None:
        raise NoEncontrado("producto no encontrado")
    if extra is None:
        raise NoEncontrado("extra no encontrado")
    if not extra.es_extra:
        raise Conflicto(f"{extra.nombre} no está marcado como extra")
    if producto.es_extra:
        raise Conflicto("un extra no admite extras")
    if repo.admite_extra(producto_id, extra_id) is not None:
        raise Conflicto(f"{producto.nombre} ya admite ese extra")
    return repo.vincular_extra(producto_id, extra_id, maximo)


def editar_producto(session: Session, producto_id: uuid.UUID, **campos) -> ProductoComercial:
    prod = ProductoComercialRepo(session).get(producto_id)
    if prod is None:
        raise NoEncontrado("producto comercial no encontrado")
    for campo in ("nombre", "activo", "empaque_id", "modalidades_empaque"):
        if campo in campos and campos[campo] is not None:
            setattr(prod, campo, campos[campo])
    return prod


def listar_productos(
    session: Session, marca_id: uuid.UUID | None = None
) -> list[ProductoComercial]:
    return ProductoComercialRepo(session).list(marca_id)


def crear_medio_pago(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombre: str,
    direccion: str,
    tipo: str,
    comision_pct: Decimal = Decimal(0),
) -> MedioPago:
    return MedioPagoRepo(session).add(
        MedioPago(
            empresa_id=empresa_id,
            nombre=nombre,
            direccion=direccion,
            tipo=tipo,
            comision_pct=comision_pct,
        )
    )


def listar_medios_pago(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[MedioPago]:
    return MedioPagoRepo(session).list(empresa_id)
