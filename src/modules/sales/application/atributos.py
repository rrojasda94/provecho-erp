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

from src.modules.inventory.application.queries_publicas import (
    ptav_usados_en_condiciones,
)
from src.modules.sales.application import catalogo as catalogo_uc
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
    ProductoVarianteValor,
    VentaItem,
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


def editar_valor(session: Session, valor_id: uuid.UUID, **campos) -> AtributoValor:
    """Campo `None` = no tocar, igual que `editar_atributo`.

    `activo=False` acá retira el valor del **catálogo** —deja de poder
    ofrecerse en productos nuevos— y no toca los PTAV que ya lo ofrecen: eso
    es `retirar_valor`, que trabaja producto por producto. Son dos niveles
    distintos y confundirlos apagaría media carta de un clic.
    """
    valor = exigir_valor(session, valor_id)
    if campos.get("nombre") is not None:
        nombre = a_titulo(campos["nombre"])
        hermanos = valores_de(session, valor.atributo_id)
        if any(v.nombre == nombre and v.id != valor.id for v in hermanos):
            atributo = exigir_atributo(session, valor.atributo_id)
            raise Conflicto(f"'{atributo.nombre}' ya tiene el valor '{nombre}'")
        valor.nombre = nombre
    for campo in ("orden", "activo"):
        if campos.get(campo) is not None:
            setattr(valor, campo, campos[campo])
    return valor


def eliminar_atributo(session: Session, atributo_id: uuid.UUID) -> None:
    """Borra el atributo y sus valores, solo si ningún producto lo ofrece.

    No hay desactivación: `atributo` no tiene columna `activo` y no se le
    agrega una para el caso raro de haberse equivocado al tipear el nombre.
    En cuanto un producto lo ofrece, el camino es sacárselo a ese producto
    (`quitar_linea`) y recién entonces borrarlo — que además obliga a mirar
    qué se está desarmando.
    """
    atributo = exigir_atributo(session, atributo_id)
    en_uso = list(
        session.scalars(
            select(ProductoComercial.nombre)
            .join(
                ProductoAtributoLinea,
                ProductoAtributoLinea.producto_comercial_id == ProductoComercial.id,
            )
            .where(ProductoAtributoLinea.atributo_id == atributo_id)
            .order_by(ProductoComercial.nombre)
        )
    )
    if en_uso:
        raise Conflicto(
            f"'{atributo.nombre}' lo ofrecen {len(en_uso)} productos "
            f"({', '.join(en_uso[:3])}{'…' if len(en_uso) > 3 else ''}); "
            "quitáselo primero"
        )
    for valor in valores_de(session, atributo_id):
        session.delete(valor)
    # El flush intermedio no es decorativo: no hay `relationship()` entre
    # `atributo` y `atributo_valor`, así que SQLAlchemy no conoce la
    # dependencia y ordena los DELETE al revés — la FK lo rechaza.
    session.flush()
    session.delete(atributo)


def quitar_linea(
    session: Session, *, producto_id: uuid.UUID, atributo_id: uuid.UUID
) -> None:
    """El producto deja de ofrecer el atributo, con sus PTAV.

    Se borra de verdad, y por eso hay tres guardas antes: un PTAV que alguna
    variante materializa, que una exclusión nombra, o que condiciona una línea
    de receta, no se puede borrar sin dejar huérfano a alguien. El caso caro es
    el tercero (ADR-056 §3): la línea dejaría de descontar sin avisar.
    """
    linea = session.scalar(
        select(ProductoAtributoLinea).where(
            ProductoAtributoLinea.producto_comercial_id == producto_id,
            ProductoAtributoLinea.atributo_id == atributo_id,
        )
    )
    if linea is None:
        raise NoEncontrado("el producto no ofrece ese atributo")
    ptav = ptav_de_linea(session, linea.id)
    ids = [p.id for p in ptav]
    if ids:
        _exigir_ptav_sin_uso(session, ids)
    for p in ptav:
        session.delete(p)
    # Igual que en `eliminar_atributo`: sin `relationship()` declarada hay que
    # forzar el orden, o el DELETE de la línea sale antes que el de sus PTAV.
    session.flush()
    session.delete(linea)


def _exigir_ptav_sin_uso(session: Session, ptav_ids: list[uuid.UUID]) -> None:
    en_variantes = session.scalar(
        select(ProductoVarianteValor).where(
            ProductoVarianteValor.producto_atributo_valor_id.in_(ptav_ids)
        )
    )
    if en_variantes is not None:
        raise Conflicto(
            "hay variantes generadas con esos valores; desactivalas antes de "
            "quitar el atributo"
        )
    en_exclusiones = session.scalar(
        select(ProductoExclusion).where(
            ProductoExclusion.producto_atributo_valor_id.in_(ptav_ids)
            | ProductoExclusion.excluye_valor_id.in_(ptav_ids)
        )
    )
    if en_exclusiones is not None:
        raise Conflicto(
            "esos valores están en una exclusión; deshacela antes de quitar "
            "el atributo"
        )
    if _alguno_vendido(session, ptav_ids):
        raise Conflicto(
            "hay ventas que nombran esos valores; el atributo se queda para que "
            "las comandas viejas sigan diciendo qué se preparó"
        )
    en_recetas = ptav_usados_en_condiciones(session, ptav_ids)
    if en_recetas:
        raise Conflicto(
            f"{len(en_recetas)} de esos valores condicionan líneas de receta; "
            "sacá la condición antes de quitar el atributo"
        )


def _alguno_vendido(session: Session, ptav_ids: list[uuid.UUID]) -> bool:
    """¿Alguna línea de venta eligió uno de estos valores?

    `venta_item.valores_variante_ids` es JSONB (ADR-055) y se compara en
    Python por lo mismo que `ptav_usados_en_condiciones`: la consulta
    equivalente se escribe distinto en SQLite y en Postgres. Solo se leen las
    líneas que eligieron algo, que son las de productos con atributos.
    """
    buscados = {str(identificador) for identificador in ptav_ids}
    for elegidos in session.scalars(
        select(VentaItem.valores_variante_ids).where(
            VentaItem.valores_variante_ids.isnot(None)
        )
    ):
        if buscados & {str(valor) for valor in elegidos or []}:
            return True
    return False


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


def atributos_de_receta(session: Session, receta_id: uuid.UUID) -> list[dict]:
    """Los ejes con los que se puede condicionar una línea de esta receta.

    Cierra el hueco que ADR-058 dejó anotado: *"la ficha de receta suelta no
    sabe qué producto usa la receta, así que solo podría mostrar UUID"*. El
    camino inverso —de la receta a los productos que la usan y de ahí a lo que
    ofrecen, padre incluido— se responde acá porque las tablas son de `sales`.

    Lista vacía = ningún producto usa esta receta. La pantalla esconde la
    columna, que es más honesto que ofrecer una condición sin nombres.
    """
    productos = list(
        session.scalars(
            select(ProductoComercial).where(ProductoComercial.receta_id == receta_id)
        )
    )
    if not productos:
        return []
    ofrecidos: set[str] = set()
    for producto in productos:
        ofrecidos |= catalogo_uc.valores_ofrecidos(session, producto)
    if not ofrecidos:
        return []
    filas = session.execute(
        select(
            Atributo.id,
            Atributo.nombre,
            Atributo.orden,
            ProductoAtributoValor.id,
            AtributoValor.nombre,
            AtributoValor.orden,
        )
        .select_from(ProductoAtributoValor)
        .join(
            ProductoAtributoLinea,
            ProductoAtributoValor.linea_id == ProductoAtributoLinea.id,
        )
        .join(Atributo, Atributo.id == ProductoAtributoLinea.atributo_id)
        .join(AtributoValor, AtributoValor.id == ProductoAtributoValor.atributo_valor_id)
        .where(ProductoAtributoValor.id.in_([uuid.UUID(v) for v in ofrecidos]))
        .order_by(Atributo.orden, Atributo.nombre, AtributoValor.orden, AtributoValor.nombre)
    )
    ejes: dict[uuid.UUID, dict] = {}
    for atributo_id, atributo, _orden, ptav_id, valor, _orden_valor in filas:
        eje = ejes.setdefault(
            atributo_id, {"id": atributo_id, "nombre": atributo, "valores": []}
        )
        eje["valores"].append({"id": ptav_id, "nombre": valor})
    return list(ejes.values())


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
    session: Session,
    ptav_id: uuid.UUID,
    *,
    precio_extra: Decimal | None = None,
    activo: bool | None = None,
) -> ProductoAtributoValor:
    """Cuánto suma este valor al precio de lista (RN-PRC-003 sigue mandando
    sobre el precio base), y si sigue ofreciéndose.

    `activo` entra acá y no en un endpoint aparte porque `retirar_valor` solo
    sabe apagar: sin esto, retirar un valor por error era irreversible y la
    única salida era volver a colgar el atributo entero.
    """
    ptav = session.get(ProductoAtributoValor, ptav_id)
    if ptav is None:
        raise NoEncontrado("valor de producto no encontrado")
    if precio_extra is not None:
        if precio_extra < 0:
            raise ReglaNegocio("el precio extra no puede ser negativo")
        ptav.precio_extra = precio_extra
    if activo is not None:
        ptav.activo = activo
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
