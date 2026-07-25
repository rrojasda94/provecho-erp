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
        )
    )


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
