"""Opciones de una línea del carrito —extras y sabores (Mitad x Mitad)—:
reglas puras, sin infraestructura.

Son las mismas que `sales` hace cumplir al crear la venta (RN-COM-021/023/038/
040): extras que el producto admite, tope por extra, mínimo y máximo por grupo,
un valor por atributo y pares excluidos. Se repiten acá **antes de cobrar**: con
Izipay el pedido se paga primero y recién después se convierte en venta, y una
línea que `sales` rechazara ahí dejaría al cliente con el pago hecho y sin
pedido. La fuente de lo que se ofrece es la misma carta que ve el cliente
(`sales.queries_publicas.carta_publica`), así que pantalla, checkout y venta
hablan de lo mismo.

El precio nunca viene del navegador: sale de la carta (RN-PRC-003), y acá solo se
suma lo que la carta declara para lo elegido.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

#: Regla de la marca, no del ERP (`majambo.md` §3.1.8): a una pizza se le suman
#: como mucho 3 extras de pago. No cuenta lo que forma parte de la pizza —el
#: sabor de un grupo obligatorio—, solo lo que el cliente agrega y paga aparte.
MAXIMO_EXTRAS_DE_PAGO_POR_LINEA = 3


@dataclass(frozen=True)
class ExtraOfrecido:
    id: uuid.UUID
    nombre: str
    precio: Decimal
    maximo: int | None
    grupo_id: uuid.UUID | None


@dataclass(frozen=True)
class GrupoOfrecido:
    id: uuid.UUID
    nombre: str | None
    minimo: int
    maximo: int | None


@dataclass(frozen=True)
class ValorOfrecido:
    nombre: str
    precio_extra: Decimal


@dataclass(frozen=True)
class AtributoOfrecido:
    nombre: str
    valores: dict[uuid.UUID, ValorOfrecido]


@dataclass(frozen=True)
class OpcionesNodo:
    """Lo que ofrece un producto o una presentación para armar la línea."""

    extras: dict[uuid.UUID, ExtraOfrecido] = field(default_factory=dict)
    grupos: dict[uuid.UUID, GrupoOfrecido] = field(default_factory=dict)
    atributos: tuple[AtributoOfrecido, ...] = ()
    exclusiones: frozenset[frozenset[uuid.UUID]] = frozenset()


@dataclass(frozen=True)
class Evaluacion:
    """Lo elegido, ya validado y con su precio por unidad de la línea."""

    recargo_valores: Decimal
    extras_por_unidad: Decimal
    extras: tuple[tuple[ExtraOfrecido, int], ...]
    valores: tuple[tuple[uuid.UUID, ValorOfrecido], ...]


def _de_pago(extra: ExtraOfrecido, grupos: dict[uuid.UUID, GrupoOfrecido]) -> bool:
    grupo = grupos.get(extra.grupo_id) if extra.grupo_id is not None else None
    return grupo is None or grupo.minimo == 0


def _validar_extras(
    opciones: OpcionesNodo, pedidos: tuple[tuple[uuid.UUID, int], ...]
) -> tuple[tuple[ExtraOfrecido, int], ...]:
    ids = [i for i, _ in pedidos]
    if len(set(ids)) != len(ids):
        raise ValueError("un extra no puede repetirse: usa su cantidad")
    elegidos = []
    for extra_id, cantidad in pedidos:
        extra = opciones.extras.get(extra_id)
        if extra is None:
            raise ValueError("uno de los extras ya no se ofrece para este producto")
        if extra.maximo is not None and cantidad > extra.maximo:
            raise ValueError(f"«{extra.nombre}» admite hasta {extra.maximo} por unidad")
        elegidos.append((extra, cantidad))

    de_pago = sum(c for e, c in elegidos if _de_pago(e, opciones.grupos))
    if de_pago > MAXIMO_EXTRAS_DE_PAGO_POR_LINEA:
        raise ValueError(
            f"máximo {MAXIMO_EXTRAS_DE_PAGO_POR_LINEA} extras por producto"
        )

    _validar_grupos(opciones.grupos, [e for e, _ in elegidos])
    return tuple(elegidos)


def _validar_grupos(
    grupos: dict[uuid.UUID, GrupoOfrecido], elegidos: list[ExtraOfrecido]
) -> None:
    """Cuántas opciones exige cada grupo (RN-COM-023): se cuenta una por extra
    elegido, no por unidad, igual que `sales`."""
    por_grupo: dict[uuid.UUID, int] = {}
    for extra in elegidos:
        if extra.grupo_id is not None:
            por_grupo[extra.grupo_id] = por_grupo.get(extra.grupo_id, 0) + 1
    for grupo in grupos.values():
        cuantos = por_grupo.get(grupo.id, 0)
        etiqueta = grupo.nombre or "una opción"
        if cuantos < grupo.minimo:
            raise ValueError(f"falta elegir {etiqueta}")
        if grupo.maximo is not None and cuantos > grupo.maximo:
            raise ValueError(f"{etiqueta} admite hasta {grupo.maximo}")


def _validar_valores(
    opciones: OpcionesNodo, pedidos: tuple[uuid.UUID, ...]
) -> tuple[tuple[uuid.UUID, ValorOfrecido], ...]:
    if len(set(pedidos)) != len(pedidos):
        raise ValueError("una opción no puede repetirse")
    ofrecidos = {v_id: v for a in opciones.atributos for v_id, v in a.valores.items()}
    if any(v not in ofrecidos for v in pedidos):
        raise ValueError("una de las opciones ya no se ofrece para este producto")
    for atributo in opciones.atributos:
        cuantas = sum(1 for v in pedidos if v in atributo.valores)
        if cuantas == 0:
            raise ValueError(f"falta elegir {atributo.nombre}")
        if cuantas > 1:
            raise ValueError(f"elige una sola opción de {atributo.nombre}")
    elegidas = set(pedidos)
    if any(par <= elegidas for par in opciones.exclusiones):
        raise ValueError("esa combinación no se puede pedir: elige opciones distintas")
    return tuple((v, ofrecidos[v]) for v in pedidos)


def evaluar(
    opciones: OpcionesNodo,
    extras: tuple[tuple[uuid.UUID, int], ...],
    valores: tuple[uuid.UUID, ...],
) -> Evaluacion:
    """Valida lo elegido contra lo que el producto ofrece y calcula lo que suma
    por unidad. Lanza `ValueError` con un mensaje que se le puede mostrar al
    cliente."""
    extras_ok = _validar_extras(opciones, extras)
    valores_ok = _validar_valores(opciones, valores)
    return Evaluacion(
        recargo_valores=sum((v.precio_extra for _, v in valores_ok), Decimal(0)),
        extras_por_unidad=sum((e.precio * c for e, c in extras_ok), Decimal(0)),
        extras=extras_ok,
        valores=valores_ok,
    )
