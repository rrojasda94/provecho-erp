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
from src.shared import fechas


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
    if ProductoComercialRepo(session).variantes_de(producto_comercial_id):
        raise Conflicto(
            f"'{producto.nombre}' se vende por variante: el precio va en cada "
            "una (RN-COM-022)"
        )
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
    fecha = fecha or fechas.hoy()
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


def _extras_de(repo, producto, por_id: dict, precio_de: dict) -> list[dict]:
    """Los extras que ofrece **este** producto, con el grupo de cada uno.

    Se llama una vez por el padre y una vez por cada variante, y usa los
    **efectivos**: lo propio más lo heredado del padre (ADR-042). Los grupos
    pueden estar colgados de cualquiera de los dos —el seeder los pone en la
    variante, el lienzo en el padre— y de dónde quedaron no debería decidir
    si la carta los muestra.
    """
    grupos_por_id = {g.id: g for g in repo.grupos_efectivos(producto)}
    extras = []
    for vinculo in repo.extras_efectivos(producto):
        extra = por_id.get(vinculo.extra_id)
        # Un extra sin precio vigente en este ámbito no se ofrece,
        # mismo criterio que un producto sin precio.
        if extra is None or vinculo.extra_id not in precio_de:
            continue
        grupo = grupos_por_id.get(vinculo.grupo_id)
        extras.append(
            {
                "producto_comercial_id": extra.id,
                "nombre": extra.nombre,
                "precio_unitario": precio_de[extra.id],
                "maximo": vinculo.maximo,
                "grupo_id": vinculo.grupo_id,
                "grupo_nombre": grupo.nombre if grupo else None,
                "grupo_minimo": grupo.minimo if grupo else 0,
                "grupo_maximo": grupo.maximo if grupo else None,
            }
        )
    return extras


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
    resuelto, sus variantes y los extras que admite cada uno.

    Lo que no se puede vender no se muestra: un producto simple sin precio
    vigente queda fuera, y uno con variantes queda fuera si ninguna de sus
    variantes tiene precio. Las variantes no salen sueltas en la grilla
    —aparecen dentro de su padre (RN-COM-022)—, igual que los extras
    (RN-COM-021).

    Cada variante trae **sus propios** extras: una Familiar y una Personal no
    ofrecen los mismos sabores ni los mismos agregados.
    """
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
        if producto.es_extra or producto.producto_padre_id is not None:
            continue
        variantes = [
            {
                "producto_comercial_id": v.id,
                "nombre": v.nombre,
                "precio_unitario": precio_de[v.id],
                "orden": v.orden,
                "extras": _extras_de(repo, v, por_id, precio_de),
            }
            for v in repo.variantes_de(producto.id)
            if v.id in precio_de
        ]
        # El precio de la tarjeta con variantes es el "desde": el que se
        # cobra sale de la variante elegida.
        precio = min((v["precio_unitario"] for v in variantes), default=None)
        if precio is None:
            precio = precio_de.get(producto.id)
        if precio is None:
            continue
        extras = _extras_de(repo, producto, por_id, precio_de)
        items.append(
            {
                "producto_comercial_id": producto.id,
                "id_interno": producto.id_interno,
                "nombre": producto.nombre,
                "categoria_id": producto.categoria_id,
                "categoria_nombre": nombre_categoria.get(producto.categoria_id),
                "precio_unitario": precio,
                "variantes": sorted(variantes, key=lambda v: (v["orden"], v["nombre"])),
                "extras": extras,
            }
        )
    return items
