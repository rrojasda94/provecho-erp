"""Precio server-side (RN-PRC-003): el sistema fija el precio, el PDV lo lee.

El cliente nunca envía el monto a cobrar. Confirmar una venta resuelve el
precio de cada ítem contra las listas vigentes para
(marca, sucursal, canal, modalidad, fecha).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

# `categoria` es la misma tabla a la que `producto_comercial.categoria_id`
# ya apunta por FK (ver ese modelo): un agrupador genérico por empresa, sin
# lógica de dominio propia. Leer su nombre acá no es cruzar el dominio de
# inventory, es seguir la referencia que sales ya tiene.
from src.modules.inventory.infrastructure.models.categoria import Categoria
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    PrecioNoDefinido,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    ListaPrecio,
    Precio,
    ProductoComercial,
)
from src.modules.sales.infrastructure.repositories import (
    ListaPrecioRepo,
    PrecioRepo,
    ProductoComercialRepo,
)


def crear_lista(
    session: Session,
    *,
    marca_id: uuid.UUID,
    nombre: str,
    vigente_desde: date,
    vigente_hasta: date | None = None,
    sucursal_id: uuid.UUID | None = None,
    canal: str | None = None,
    modalidad: str | None = None,
    es_promocional: bool = False,
) -> ListaPrecio:
    if canal is not None and canal not in rules.CANALES:
        raise Conflicto(f"canal inválido: {canal}")
    if modalidad is not None and modalidad not in rules.MODALIDADES:
        raise Conflicto(f"modalidad inválida: {modalidad}")
    if vigente_hasta is not None and vigente_hasta < vigente_desde:
        raise Conflicto("vigente_hasta anterior a vigente_desde")
    if es_promocional and vigente_hasta is None:
        # Una promoción sin fin no se restaura sola (RN-PRM-001).
        raise Conflicto("una lista promocional exige vigente_hasta")
    return ListaPrecioRepo(session).add(
        ListaPrecio(
            marca_id=marca_id,
            nombre=nombre,
            sucursal_id=sucursal_id,
            canal=canal,
            modalidad=modalidad,
            es_promocional=es_promocional,
            vigente_desde=vigente_desde,
            vigente_hasta=vigente_hasta,
        )
    )


def listar_listas(
    session: Session, marca_id: uuid.UUID | None = None
) -> list[ListaPrecio]:
    return ListaPrecioRepo(session).list(marca_id)


def fijar_precio(
    session: Session,
    *,
    lista_precio_id: uuid.UUID,
    producto_comercial_id: uuid.UUID,
    monto: Decimal,
) -> Precio:
    """Alta de precio en una lista. No hay edición: corregir = lista nueva."""
    lista = ListaPrecioRepo(session).get(lista_precio_id)
    if lista is None or lista.deleted_at is not None:
        raise NoEncontrado("lista de precios no encontrada")
    producto = ProductoComercialRepo(session).get(producto_comercial_id)
    if producto is None:
        raise NoEncontrado("producto comercial no encontrado")
    if producto.marca_id != lista.marca_id:
        raise Conflicto("el producto no pertenece a la marca de la lista")
    if monto < 0:
        raise Conflicto("el precio no puede ser negativo")
    repo = PrecioRepo(session)
    if producto_comercial_id in {
        p.producto_comercial_id for p in repo.de_lista(lista_precio_id)
    }:
        raise Conflicto("el producto ya tiene precio en esta lista")
    return repo.add(
        Precio(
            lista_precio_id=lista_precio_id,
            producto_comercial_id=producto_comercial_id,
            monto=monto,
        )
    )


def resolver_precio(
    session: Session,
    *,
    producto: ProductoComercial,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    fecha: date | None = None,
) -> Decimal:
    fecha = fecha or date.today()
    listas = ListaPrecioRepo(session).vigentes(
        marca_id=producto.marca_id,
        sucursal_id=sucursal_id,
        canal=canal,
        modalidad=modalidad,
        fecha=fecha,
    )
    montos = PrecioRepo(session).por_producto(
        producto.id, [lp.id for lp in listas]
    )
    elegida = rules.elegir_lista_precio([lp for lp in listas if lp.id in montos])
    if elegida is None:
        raise PrecioNoDefinido(
            f"'{producto.nombre}' no tiene precio vigente para "
            f"canal={canal}, modalidad={modalidad}"
        )
    return montos[elegida.id]


def carta(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    marca_id: uuid.UUID | None = None,
    fecha: date | None = None,
) -> list[dict]:
    """Lo que el PDV/kiosko renderiza: productos activos con su precio ya
    resuelto y los extras que admite cada uno. Los que no tienen precio
    vigente no se muestran (no se pueden vender)."""
    repo = ProductoComercialRepo(session)
    precio_de = {}
    productos = repo.list(marca_id)
    for producto in productos:
        try:
            precio_de[producto.id] = resolver_precio(
                session,
                producto=producto,
                sucursal_id=sucursal_id,
                canal=canal,
                modalidad=modalidad,
                fecha=fecha,
            )
        except PrecioNoDefinido:
            continue

    por_id = {p.id: p for p in productos}
    categoria_ids = {p.categoria_id for p in productos if p.categoria_id}
    nombre_categoria = {
        c.id: c.nombre
        for c in session.scalars(
            select(Categoria).where(Categoria.id.in_(categoria_ids))
        )
    }
    items = []
    for producto in productos:
        # Los extras no se listan sueltos: salen dentro del producto que
        # los admite (RN-COM-021).
        if producto.es_extra or producto.id not in precio_de:
            continue
        extras = []
        for vinculo in repo.extras_de(producto.id):
            extra = por_id.get(vinculo.extra_id)
            # Un extra sin precio vigente en este ámbito no se ofrece,
            # mismo criterio que un producto sin precio.
            if extra is None or vinculo.extra_id not in precio_de:
                continue
            extras.append(
                {
                    "producto_comercial_id": extra.id,
                    "nombre": extra.nombre,
                    "precio_unitario": precio_de[extra.id],
                    "maximo": vinculo.maximo,
                }
            )
        items.append(
            {
                "producto_comercial_id": producto.id,
                "id_interno": producto.id_interno,
                "nombre": producto.nombre,
                "categoria_id": producto.categoria_id,
                "categoria_nombre": nombre_categoria.get(producto.categoria_id),
                "precio_unitario": precio_de[producto.id],
                "extras": extras,
            }
        )
    return items
