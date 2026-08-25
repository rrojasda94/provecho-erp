"""Generador de combinaciones: los atributos `siempre` se vuelven filas hijas.

Es el `create_variant_ids = 'always'` de Odoo (ADR-055 §3), lo único de aquel
ADR que había quedado sin construir. La variante generada **sigue siendo un
`producto_comercial`** —no una tabla nueva— y por eso precio, margen, ruteo del
KDS, carta y réplica al hub la entienden sin escribir una línea.

Los otros dos modos no pasan por acá y es a propósito:

- `nunca` no materializa nada. Es el caso de `Mitad 1` x `Mitad 2`: 361
  combinaciones que serían 361 filas se resuelven con **una** receta de líneas
  condicionadas (ADR-056).
- `dinamica` materializa en la primera venta, así que vive en el camino del
  cobro y no acá. Todavía no está construido — ver la deuda de `sales`.
"""

import itertools
import uuid

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
    ProductoVarianteValor,
)
from src.modules.sales.infrastructure.models.precio import Precio

#: `producto_comercial.id_interno` es `String(4)`: una letra de familia y tres
#: dígitos en base 36. Mismo formato que `scripts/odoo/convertir_catalogo.py`,
#: para que un código generado acá y uno importado se lean igual.
ALFABETO = "0123456789abcdefghijklmnopqrstuvwxyz"
_ANCHO = 3
_LARGO_NOMBRE = 150


def generar_variantes(
    session: Session, producto_id: uuid.UUID
) -> list[ProductoComercial]:
    """Materializa las combinaciones que falten. Devuelve solo las creadas.

    **Es idempotente**: volver a llamarla no crea nada, porque cada hija se
    identifica por su conjunto de PTAV en `producto_variante_valor` y las que
    ya existen se saltan. Eso es lo que permite agregarle un sabor al atributo
    y volver a apretar el botón sin duplicar las once combinaciones anteriores.

    Tampoco toca ni desactiva lo que ya está: una variante puede tener ventas,
    y bajar el atributo de `siempre` a `nunca` deja de generar sin borrar
    (RN-COM-039).
    """
    producto = session.get(ProductoComercial, producto_id)
    if producto is None:
        raise NoEncontrado("producto comercial no encontrado")
    _exigir_padre_generable(producto)

    ejes = _ejes_materializables(session, producto_id)
    if not ejes:
        raise ReglaNegocio(
            "ningún atributo de este producto materializa variantes: pasá "
            "alguno a modo 'siempre' o elegí los valores en la venta"
        )

    todos = [p for eje in ejes for p in eje]
    prohibidos = _pares_excluidos(session, [p.id for p in todos])
    nombres = _nombres_de_valores(session, todos)
    ya_estan = _combinaciones_existentes(session, producto_id)
    codigos = _codigos_tomados(session)
    prefijo = producto.id_interno[:1] or "V"

    creadas: list[ProductoComercial] = []
    for orden, combinacion in enumerate(itertools.product(*ejes)):
        ptav_ids = frozenset(p.id for p in combinacion)
        if ptav_ids in ya_estan or _tiene_par_prohibido(ptav_ids, prohibidos):
            continue
        codigo = _codigo_libre(codigos, prefijo)
        codigos.add(codigo)
        hija = ProductoComercial(
            id_interno=codigo,
            marca_id=producto.marca_id,
            nombre=_nombre_compuesto(producto.nombre, combinacion, nombres),
            categoria_id=producto.categoria_id,
            # Nace sin receta a propósito: no hay ninguna de dónde copiarla
            # —el padre no puede tener— y exigirla acá haría imposible el
            # generador. Queda como pendiente visible en la ficha.
            receta_id=None,
            producto_padre_id=producto.id,
            orden=orden,
            empaque_id=producto.empaque_id,
            modalidades_empaque=producto.modalidades_empaque,
        )
        session.add(hija)
        session.flush()
        for ptav in combinacion:
            session.add(
                ProductoVarianteValor(
                    producto_comercial_id=hija.id, producto_atributo_valor_id=ptav.id
                )
            )
        ya_estan.add(ptav_ids)
        creadas.append(hija)
    session.flush()
    return creadas


def sin_precio(session: Session, productos: list[ProductoComercial]) -> list[str]:
    """Cuáles de estas variantes no figuran en **ninguna** lista de precios.

    `precios.carta()` descarta en silencio al producto que `resolver_precio`
    no sabe cobrar, así que sin este aviso alguien genera doce combinaciones,
    no ve ninguna en el PDV y no tiene forma de saber por qué.

    Se pregunta "¿está en alguna lista?" y no "¿tiene precio vigente acá y
    ahora?" a propósito: lo segundo necesita sucursal, canal y modalidad, que
    la ficha del catálogo no tiene, y contestaría "sin precio" para una
    variante que sí se vende en otra sucursal.
    """
    if not productos:
        return []
    ids = [p.id for p in productos]
    con_precio = set(
        session.scalars(
            select(Precio.producto_comercial_id).where(
                Precio.producto_comercial_id.in_(ids)
            )
        )
    )
    return [p.nombre for p in productos if p.id not in con_precio]


def _exigir_padre_generable(producto: ProductoComercial) -> None:
    """Las mismas tres reglas que `catalogo._validar_padre` (RN-COM-022), del
    lado del padre: un extra no tiene variantes, una variante no tiene
    variantes propias, y un producto con receta propia se vende por sí mismo.
    """
    if producto.es_extra:
        raise Conflicto("un extra no admite variantes")
    if producto.producto_padre_id is not None:
        raise Conflicto(
            f"'{producto.nombre}' ya es una variante: no admite variantes propias"
        )
    if producto.receta_id is not None:
        raise Conflicto(
            f"'{producto.nombre}' tiene receta propia. Un producto con variantes no "
            "se prepara ni se vende por sí mismo: quítale la receta y pásala a "
            "su primera variante"
        )


def _ejes_materializables(
    session: Session, producto_id: uuid.UUID
) -> list[list[ProductoAtributoValor]]:
    """Un eje por atributo en modo `siempre`, con sus valores activos.

    Un eje sin valores activos —todos retirados— vacía el producto cartesiano
    entero, así que se descarta el eje en vez de devolver cero combinaciones
    sin explicación.
    """
    lineas = session.execute(
        select(ProductoAtributoLinea, Atributo)
        .join(Atributo, Atributo.id == ProductoAtributoLinea.atributo_id)
        .where(ProductoAtributoLinea.producto_comercial_id == producto_id)
        .order_by(ProductoAtributoLinea.orden, Atributo.orden, Atributo.nombre)
    ).all()
    ejes = []
    for linea, atributo in lineas:
        if not rules.combinaciones_a_generar(atributo.modo_variante):
            continue
        valores = list(
            session.scalars(
                select(ProductoAtributoValor)
                .join(
                    AtributoValor,
                    AtributoValor.id == ProductoAtributoValor.atributo_valor_id,
                )
                .where(
                    ProductoAtributoValor.linea_id == linea.id,
                    ProductoAtributoValor.activo.is_(True),
                    AtributoValor.activo.is_(True),
                )
                .order_by(AtributoValor.orden, AtributoValor.nombre)
            )
        )
        if valores:
            ejes.append(valores)
    return ejes


def _pares_excluidos(
    session: Session, ptav_ids: list[uuid.UUID]
) -> set[frozenset[uuid.UUID]]:
    """Todas las exclusiones que tocan a estos valores, en una sola consulta.

    `catalogo.combinacion_excluida` responde lo mismo pero pregunta a la base
    una vez por combinación, y acá las combinaciones son un producto
    cartesiano: con tres tamaños y cuatro masas son doce consultas para leer
    una tabla que entra entera en memoria. El par se guarda una vez y vale en
    los dos sentidos (RN-COM-038), y un `frozenset` es exactamente eso.
    """
    if not ptav_ids:
        return set()
    filas = session.execute(
        select(
            ProductoExclusion.producto_atributo_valor_id,
            ProductoExclusion.excluye_valor_id,
        ).where(
            ProductoExclusion.producto_atributo_valor_id.in_(ptav_ids),
            ProductoExclusion.excluye_valor_id.in_(ptav_ids),
        )
    )
    return {frozenset((uno, otro)) for uno, otro in filas}


def _tiene_par_prohibido(
    ptav_ids: frozenset[uuid.UUID], prohibidos: set[frozenset[uuid.UUID]]
) -> bool:
    return any(
        frozenset(par) in prohibidos for par in itertools.combinations(ptav_ids, 2)
    )


def _combinaciones_existentes(
    session: Session, producto_id: uuid.UUID
) -> set[frozenset[uuid.UUID]]:
    """Qué combinación representa cada hija que ya existe.

    Incluye a las **inactivas**: una variante descontinuada sigue ocupando su
    combinación, y regenerarla crearía una segunda fila para el mismo plato.
    """
    filas = session.execute(
        select(
            ProductoVarianteValor.producto_comercial_id,
            ProductoVarianteValor.producto_atributo_valor_id,
        )
        .join(
            ProductoComercial,
            ProductoComercial.id == ProductoVarianteValor.producto_comercial_id,
        )
        .where(ProductoComercial.producto_padre_id == producto_id)
    )
    por_hija: dict[uuid.UUID, set[uuid.UUID]] = {}
    for hija_id, ptav_id in filas:
        por_hija.setdefault(hija_id, set()).add(ptav_id)
    return {frozenset(valores) for valores in por_hija.values()}


def _codigos_tomados(session: Session) -> set[str]:
    """`id_interno` es único en **todo** el grupo, no por empresa ni por marca,
    así que se traen todos. Una consulta por tanda y no una por variante."""
    return set(session.scalars(select(ProductoComercial.id_interno)))


def _codigo_libre(tomados: set[str], prefijo: str) -> str:
    for indice in range(len(ALFABETO) ** _ANCHO):
        resto, digitos = indice, ""
        for _ in range(_ANCHO):
            resto, digito = divmod(resto, len(ALFABETO))
            digitos = ALFABETO[digito] + digitos
        codigo = prefijo + digitos
        if codigo not in tomados:
            return codigo
    raise ReglaNegocio(
        f"no quedan códigos libres con el prefijo '{prefijo}': renombrá el "
        "producto padre o liberá variantes viejas"
    )


def _nombres_de_valores(
    session: Session, ptav: list[ProductoAtributoValor]
) -> dict[uuid.UUID, str]:
    """`ptav.id` → nombre del valor, en una consulta.

    `ProductoAtributoValor` no tiene relación cargada hacia `AtributoValor` y
    resolverla por fila sería una consulta por combinación por eje.
    """
    if not ptav:
        return {}
    filas = session.execute(
        select(ProductoAtributoValor.id, AtributoValor.nombre)
        .join(AtributoValor, AtributoValor.id == ProductoAtributoValor.atributo_valor_id)
        .where(ProductoAtributoValor.id.in_([p.id for p in ptav]))
    )
    return {ptav_id: nombre for ptav_id, nombre in filas}


def _nombre_compuesto(
    padre: str,
    combinacion: tuple[ProductoAtributoValor, ...],
    nombres: dict[uuid.UUID, str],
) -> str:
    """"Pizza Peperoni (Familiar, Masa Delgada)", como los nombra Odoo.

    Se recorta a `String(150)` **acá y no en la base**: Postgres rechaza el
    INSERT y SQLite lo trunca en silencio, así que dejarlo librado al motor es
    una prueba en verde y un 500 en producción.
    """
    valores = ", ".join(nombres.get(ptav.id, "?") for ptav in combinacion)
    nombre = f"{padre} ({valores})"
    if len(nombre) <= _LARGO_NOMBRE:
        return nombre
    sobra = len(nombre) - _LARGO_NOMBRE
    return f"{padre[: max(1, len(padre) - sobra - 1)]}… ({valores})"[:_LARGO_NOMBRE]
