"""Casos de uso de atributos, valores y lo que cada producto ofrece (ADR-055).

Tres niveles y cada uno existe por una razón distinta:

- **`atributo` + `atributo_valor`** son del catálogo de la empresa. "Tamaño"
  con Personal/Mediana/Familiar se nombra una vez y lo usan cuarenta
  productos.
- **`producto_atributo_linea`** dice qué atributo ofrece un producto.
- **`producto_atributo_valor` (PTAV)** dice qué valores de ese atributo
  ofrece *ese* producto, y es donde vive el sobreprecio: "Familiar" cuesta
  distinto en una pizza que en una lasaña.

Borrar es lo delicado. Un valor que alguna venta ya nombró, o que una línea de
receta usa como condición, no se puede sacar de la base sin dejar huérfano a
alguien — así que se **desactiva**: deja de ofrecerse y las ventas viejas
siguen diciendo qué se preparó. Solo se borra de verdad lo que nadie tocó.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    Atributo,
    AtributoValor,
    ProductoAtributoLinea,
    ProductoAtributoValor,
    ProductoComercial,
    ProductoExclusion,
)
from src.shared.texto import a_titulo

LARGO_NOMBRE = 80


def crear_atributo(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombre: str,
    modo_variante: str = "nunca",
    display: str = "radio",
    orden: int = 0,
) -> Atributo:
    nombre = a_titulo(nombre)
    _validar_vocabulario(modo_variante, display)
    if _por_nombre(session, empresa_id, nombre) is not None:
        raise Conflicto(f"ya existe un atributo '{nombre}'")
    atributo = Atributo(
        empresa_id=empresa_id,
        nombre=nombre,
        modo_variante=modo_variante,
        display=display,
        orden=orden,
    )
    session.add(atributo)
    session.flush()
    return atributo


def _validar_vocabulario(modo_variante: str, display: str) -> None:
    if modo_variante not in rules.MODOS_VARIANTE:
        raise ReglaNegocio(
            f"modo de variante inválido: {modo_variante}. "
            f"Admitidos: {', '.join(sorted(rules.MODOS_VARIANTE))}"
        )
    if display not in rules.DISPLAYS_ATRIBUTO:
        raise ReglaNegocio(
            f"forma de mostrar inválida: {display}. "
            f"Admitidas: {', '.join(sorted(rules.DISPLAYS_ATRIBUTO))}"
        )


def _por_nombre(
    session: Session, empresa_id: uuid.UUID, nombre: str
) -> Atributo | None:
    return session.scalar(
        select(Atributo).where(
            Atributo.empresa_id == empresa_id, Atributo.nombre == nombre
        )
    )


def editar_atributo(session: Session, atributo_id: uuid.UUID, **campos) -> Atributo:
    """Campo `None` = no tocar.

    `modo_variante` se puede bajar de `siempre` a `nunca` en cualquier
    momento; las variantes ya materializadas **no se borran**, porque puede
    haber ventas que las nombran. Dejan de generarse nuevas, que es lo que
    alguien quiere cuando descubre que un atributo de 17 valores iba a
    materializar 289 combinaciones.
    """
    atributo = exigir_atributo(session, atributo_id)
    if campos.get("nombre") is not None:
        nombre = a_titulo(campos["nombre"])
        otro = _por_nombre(session, atributo.empresa_id, nombre)
        if otro is not None and otro.id != atributo.id:
            raise Conflicto(f"ya existe un atributo '{nombre}'")
        atributo.nombre = nombre
    _validar_vocabulario(
        campos.get("modo_variante") or atributo.modo_variante,
        campos.get("display") or atributo.display,
    )
    for campo in ("modo_variante", "display", "orden"):
        if campos.get(campo) is not None:
            setattr(atributo, campo, campos[campo])
    return atributo


def exigir_atributo(session: Session, atributo_id: uuid.UUID) -> Atributo:
    atributo = session.get(Atributo, atributo_id)
    if atributo is None:
        raise NoEncontrado("atributo no encontrado")
    return atributo


def agregar_valor(
    session: Session, atributo_id: uuid.UUID, *, nombre: str, orden: int = 0
) -> AtributoValor:
    atributo = exigir_atributo(session, atributo_id)
    nombre = a_titulo(nombre)
    if any(v.nombre == nombre for v in valores_de(session, atributo.id)):
        raise Conflicto(f"'{atributo.nombre}' ya tiene el valor '{nombre}'")
    valor = AtributoValor(atributo_id=atributo.id, nombre=nombre, orden=orden)
    session.add(valor)
    session.flush()
    return valor


def exigir_valor(session: Session, valor_id: uuid.UUID) -> AtributoValor:
    valor = session.get(AtributoValor, valor_id)
    if valor is None:
        raise NoEncontrado("valor de atributo no encontrado")
    return valor


def valores_de(session: Session, atributo_id: uuid.UUID) -> list[AtributoValor]:
    return list(
        session.scalars(
            select(AtributoValor)
            .where(AtributoValor.atributo_id == atributo_id)
            .order_by(AtributoValor.orden, AtributoValor.nombre)
        )
    )


def listar_atributos(session: Session, empresa_id: uuid.UUID | None = None) -> list[dict]:
    consulta = select(Atributo).order_by(Atributo.orden, Atributo.nombre)
    if empresa_id is not None:
        consulta = consulta.where(Atributo.empresa_id == empresa_id)
    return [
        {
            "id": a.id,
            "nombre": a.nombre,
            "modo_variante": a.modo_variante,
            "display": a.display,
            "orden": a.orden,
            "valores": [
                {"id": v.id, "nombre": v.nombre, "orden": v.orden, "activo": v.activo}
                for v in valores_de(session, a.id)
            ],
        }
        for a in session.scalars(consulta)
    ]


def ofrecer_atributo(
    session: Session,
    *,
    producto_id: uuid.UUID,
    atributo_id: uuid.UUID,
    valores: list[uuid.UUID] | None = None,
    orden: int = 0,
) -> ProductoAtributoLinea:
    """Un producto pasa a ofrecer este atributo, con estos valores.

    `valores=None` ofrece **todos** los del atributo, que es lo que quiere
    quien acaba de crearlo. Volver a llamar con otra lista **agrega** los que
    falten y no toca los que ya estaban: quitar un valor es `retirar_valor`,
    porque puede haber ventas que lo nombran.
    """
    producto = session.get(ProductoComercial, producto_id)
    if producto is None:
        raise NoEncontrado("producto comercial no encontrado")
    atributo = exigir_atributo(session, atributo_id)
    linea = session.scalar(
        select(ProductoAtributoLinea).where(
            ProductoAtributoLinea.producto_comercial_id == producto_id,
            ProductoAtributoLinea.atributo_id == atributo_id,
        )
    )
    if linea is None:
        linea = ProductoAtributoLinea(
            producto_comercial_id=producto_id, atributo_id=atributo_id, orden=orden
        )
        session.add(linea)
        session.flush()

    del_atributo = {v.id: v for v in valores_de(session, atributo.id)}
    pedidos = list(del_atributo) if valores is None else list(valores)
    ajenos = [v for v in pedidos if v not in del_atributo]
    if ajenos:
        raise ReglaNegocio(
            f"'{atributo.nombre}' no tiene {len(ajenos)} de los valores pedidos"
        )
    ya = {p.atributo_valor_id for p in ptav_de_linea(session, linea.id)}
    for valor_id in pedidos:
        if valor_id in ya:
            continue
        session.add(
            ProductoAtributoValor(linea_id=linea.id, atributo_valor_id=valor_id)
        )
    session.flush()
    return linea


def ptav_de_linea(
    session: Session, linea_id: uuid.UUID
) -> list[ProductoAtributoValor]:
    return list(
        session.scalars(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.linea_id == linea_id
            )
        )
    )


def fijar_precio_extra(
    session: Session, ptav_id: uuid.UUID, *, precio_extra: Decimal
) -> ProductoAtributoValor:
    """Cuánto suma este valor al precio de lista (RN-PRC-003 sigue mandando
    sobre el precio base)."""
    ptav = session.get(ProductoAtributoValor, ptav_id)
    if ptav is None:
        raise NoEncontrado("valor de producto no encontrado")
    if precio_extra < 0:
        raise ReglaNegocio("el precio extra no puede ser negativo")
    ptav.precio_extra = precio_extra
    return ptav


def retirar_valor(session: Session, ptav_id: uuid.UUID) -> ProductoAtributoValor:
    """Saca el valor de la oferta **sin borrarlo**.

    Borrarlo dejaría huérfanas a las ventas que lo nombran y a las líneas de
    receta que lo usan como condición. Desactivado, el PDV deja de ofrecerlo
    y la comanda de una venta vieja sigue diciendo qué se preparó.
    """
    ptav = session.get(ProductoAtributoValor, ptav_id)
    if ptav is None:
        raise NoEncontrado("valor de producto no encontrado")
    ptav.activo = False
    return ptav


def excluir(
    session: Session, *, valor_id: uuid.UUID, excluye_id: uuid.UUID
) -> ProductoExclusion:
    """Declara que estos dos valores no van juntos (RN-COM-038).

    Una sola fila para el par: es simétrico y se lee en los dos sentidos.
    """
    if valor_id == excluye_id:
        raise ReglaNegocio("un valor no se excluye a sí mismo")
    for identificador in (valor_id, excluye_id):
        if session.get(ProductoAtributoValor, identificador) is None:
            raise NoEncontrado("valor de producto no encontrado")
    ya = session.scalar(
        select(ProductoExclusion).where(
            ProductoExclusion.producto_atributo_valor_id.in_([valor_id, excluye_id]),
            ProductoExclusion.excluye_valor_id.in_([valor_id, excluye_id]),
        )
    )
    if ya is not None:
        raise Conflicto("esos dos valores ya están declarados incompatibles")
    exclusion = ProductoExclusion(
        producto_atributo_valor_id=valor_id, excluye_valor_id=excluye_id
    )
    session.add(exclusion)
    session.flush()
    return exclusion


def dejar_de_excluir(
    session: Session, *, valor_id: uuid.UUID, excluye_id: uuid.UUID
) -> None:
    exclusion = session.scalar(
        select(ProductoExclusion).where(
            ProductoExclusion.producto_atributo_valor_id.in_([valor_id, excluye_id]),
            ProductoExclusion.excluye_valor_id.in_([valor_id, excluye_id]),
        )
    )
    if exclusion is None:
        raise NoEncontrado("esos dos valores no estaban declarados incompatibles")
    session.delete(exclusion)
