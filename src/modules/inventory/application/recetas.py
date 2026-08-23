"""Casos de uso de receta: la ficha técnica de lo que se produce y se vende.

Una receta es el BOM de un producto comercial (`producto_comercial.receta_id`)
o de una subreceta (`receta.articulo_id`). Acá vive su CRUD, el duplicado
para partir de una existente y el escalado por factor.

Dos decisiones que se repiten en todo el archivo:

- **La unidad la pone el insumo, salvo que la línea diga otra cosa.** Por
  defecto la cantidad se expresa en la UdM del artículo y se redondea a los
  decimales de esa unidad (RN-GER-010), que es como está cargado todo lo de
  hoy. Desde ADR-056 la línea puede elegir otra UdM **de la misma categoría**
  (RN-UDM-005) —el aceite se compra por litros y la receta lleva 30 ml— y se
  convierte por `ratio` al descontar y al costear. No son dos verdades: la
  conversión es exacta y la unidad del artículo sigue siendo la que manda en
  el almacén.
- **La operación se evalúa en el servidor.** El campo acepta "1000/3"; el
  cliente puede mostrar el resultado mientras se teclea, pero el número que
  se guarda lo calcula `shared/aritmetica.py` a partir de la expresión, no
  el navegador. Si el cliente mandara el resultado y la expresión por
  separado, nada garantizaría que uno corresponda al otro.
"""

import re
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.inventory.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.inventory.domain import rules as domain_rules
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Receta,
    RecetaItem,
    UnidadMedida,
)
from src.modules.inventory.infrastructure.repositories import ArticuloRepo, RecetaRepo
from src.modules.sales.application.queries_publicas import productos_que_usan_receta
from src.shared.aritmetica import evaluar, redondear
from src.shared.texto import a_titulo

# `receta_item.cantidad` es Numeric(12, 4): una UdM configurada con más
# decimales que eso no puede prometer lo que la columna no guarda.
DECIMALES_MAXIMOS = 4
SUFIJO_COPIA = "(copy)"
# "Pizza (copy)" y "Pizza (copy) 3" vuelven a "Pizza" al duplicar, para que
# el sufijo no se apile copia tras copia.
_SUFIJO_AL_FINAL = re.compile(rf"\s*{re.escape(SUFIJO_COPIA)}(\s+\d+)?\s*$")
# Largo de `receta_item.expresion`: una expresión más larga que la columna se
# pierde entera, así que se prefiere no guardarla a guardarla truncada.
LARGO_EXPRESION = 60


def crear_receta(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombre: str,
    rendimiento_cantidad: Decimal,
    rendimiento_unidad_medida_id: uuid.UUID,
    articulo_id: uuid.UUID | None = None,
    flexible: bool = False,
    criterio_ajuste: str | None = None,
) -> Receta:
    nombre = a_titulo(nombre)
    repo = RecetaRepo(session)
    if repo.get_by_nombre(nombre, empresa_id):
        raise Conflicto(f"ya existe una receta '{nombre}'")
    if session.get(UnidadMedida, rendimiento_unidad_medida_id) is None:
        raise NoEncontrado("unidad de medida no encontrada")
    if articulo_id is not None:
        _exigir_articulo_de_la_empresa(session, articulo_id, empresa_id)
    if rendimiento_cantidad <= 0:
        raise ReglaNegocio("el rendimiento debe ser > 0")
    return repo.add(
        Receta(
            empresa_id=empresa_id,
            nombre=nombre,
            rendimiento_cantidad=rendimiento_cantidad,
            rendimiento_unidad_medida_id=rendimiento_unidad_medida_id,
            articulo_id=articulo_id,
            flexible=flexible,
            criterio_ajuste=criterio_ajuste,
        )
    )


def _exigir_articulo_de_la_empresa(
    session: Session, articulo_id: uuid.UUID, empresa_id: uuid.UUID
) -> Articulo:
    """Una receta no puede referirse a un artículo de otra empresa — ni como
    insumo ni como lo que produce. El 404 (y no un 403) es a propósito: para
    esta empresa ese artículo sencillamente no existe."""
    articulo = session.get(Articulo, articulo_id)
    if articulo is None or articulo.empresa_id != empresa_id:
        raise NoEncontrado("artículo no encontrado")
    return articulo


def editar_receta(session: Session, receta_id: uuid.UUID, **campos) -> Receta:
    receta = _exigir(session, receta_id)
    if campos.get("nombre") is not None:
        nombre = a_titulo(campos["nombre"])
        otra = RecetaRepo(session).get_by_nombre(nombre, receta.empresa_id)
        if otra is not None and otra.id != receta.id:
            raise Conflicto(f"ya existe una receta '{nombre}'")
        receta.nombre = nombre
    if campos.get("articulo_id") is not None:
        receta.articulo_id = _articulo_producido(session, receta, campos["articulo_id"])
    for campo in (
        "rendimiento_cantidad",
        "rendimiento_unidad_medida_id",
        "flexible",
        "criterio_ajuste",
    ):
        if campos.get(campo) is not None:
            setattr(receta, campo, campos[campo])
    if receta.rendimiento_cantidad <= 0:
        raise ReglaNegocio("el rendimiento debe ser > 0")
    return receta


TIPOS_RECETA = ("subreceta", "producto")


def listar_recetas(
    session: Session,
    empresa_id: uuid.UUID | None = None,
    *,
    tipo: str | None = None,
    categoria_id: uuid.UUID | None = None,
) -> list[dict]:
    """El filtro va al servidor y no en memoria porque el listado ya se trae
    entero: filtrar en el cliente traería igual las mil recetas."""
    if tipo is not None and tipo not in TIPOS_RECETA:
        raise ReglaNegocio(f"tipo de receta inválido: {tipo}")
    return [
        _resumen(session, r)
        for r in RecetaRepo(session).list(
            empresa_id, tipo=tipo, categoria_id=categoria_id
        )
    ]


def detalle_receta(session: Session, receta_id: uuid.UUID) -> dict:
    """La receta con sus líneas ya resueltas: nombre del insumo, su unidad,
    los decimales con los que se teclea y el costo que aporta la línea."""
    receta = _exigir(session, receta_id)
    repo = RecetaRepo(session)
    items = repo.items(receta_id)
    lineas, costo = [], Decimal(0)
    for item in items:
        articulo, udm = _articulo_y_udm(session, item.articulo_id)
        ratio_linea, ratio_articulo = ratios_de_linea(session, item, articulo)
        udm_linea = (
            session.get(UnidadMedida, item.unidad_medida_id)
            if item.unidad_medida_id
            else udm
        ) or udm
        costo_linea_valor = costo_linea(item, articulo, ratio_linea, ratio_articulo)
        costo += costo_linea_valor
        lineas.append(
            {
                "id": item.id,
                "articulo_id": articulo.id,
                "articulo_nombre": articulo.nombre,
                "unidad_medida_id": udm_linea.id,
                "unidad_medida_nombre": udm_linea.nombre,
                "decimales": _decimales(udm_linea),
                "cantidad": item.cantidad,
                "expresion": item.expresion,
                "merma_pct": item.merma_pct,
                "costo_unitario": articulo.costo_promedio,
                "costo_linea": costo_linea_valor,
            }
        )
    return {**_resumen(session, receta), "items": lineas, "costo_total": costo}


def agregar_item(
    session: Session,
    receta_id: uuid.UUID,
    *,
    articulo_id: uuid.UUID,
    cantidad: Decimal | None = None,
    expresion: str | None = None,
    merma_pct: Decimal = Decimal(0),
    unidad_medida_id: uuid.UUID | None = None,
    aplica_valores: list[str] | None = None,
    orden: int = 0,
) -> RecetaItem:
    receta = _exigir(session, receta_id)
    _exigir_articulo_de_la_empresa(session, articulo_id, receta.empresa_id)
    articulo, udm = _articulo_y_udm(session, articulo_id)
    if receta.articulo_id is not None and receta.articulo_id == articulo_id:
        raise ReglaNegocio(
            f"'{articulo.nombre}' es lo que la receta produce: no puede ser "
            "también su insumo"
        )
    udm_linea = _udm_de_linea(session, unidad_medida_id, articulo, udm)
    condicion = _condicion_normalizada(aplica_valores)
    repo = RecetaRepo(session)
    # El mismo insumo puede repetirse **si cada línea aplica a otra
    # combinación** (ADR-056): la pizza mitad-y-mitad lleva jamón en una línea
    # para unos sabores y en otra para otros. Lo que sigue prohibido es la
    # misma condición dos veces, que sí es la línea duplicada de siempre.
    if any(
        i.articulo_id == articulo_id
        and _condicion_normalizada(i.aplica_valores) == condicion
        for i in repo.items(receta_id)
    ):
        raise Conflicto(
            f"'{articulo.nombre}' ya está en la receta con esa misma condición"
        )
    valor, texto = _resolver_cantidad(cantidad, expresion, udm_linea)
    _validar_merma(merma_pct)
    return repo.add_item(
        RecetaItem(
            receta_id=receta_id,
            articulo_id=articulo_id,
            cantidad=valor,
            expresion=texto,
            merma_pct=merma_pct,
            unidad_medida_id=udm_linea.id if udm_linea is not udm else None,
            aplica_valores=list(aplica_valores) if aplica_valores else None,
            orden=orden,
        )
    )


def _udm_de_linea(
    session: Session,
    unidad_medida_id: uuid.UUID | None,
    articulo: Articulo,
    udm_articulo: UnidadMedida,
) -> UnidadMedida:
    """La unidad en la que se teclea esta línea (RN-UDM-005).

    Sin unidad propia, la del artículo — que es como funcionó siempre. Con
    una, tiene que ser de **la misma categoría**: RN-UDM-001 no admite otra
    cosa, y la conversión por `ratio` solo tiene sentido dentro de una
    categoría. Se rechaza en vez de ignorarse porque una línea que dice
    "kilos" sobre un artículo que se lleva por unidad no es un detalle de
    presentación: es un gramaje que nadie puede interpretar.
    """
    if unidad_medida_id is None or unidad_medida_id == udm_articulo.id:
        return udm_articulo
    udm = session.get(UnidadMedida, unidad_medida_id)
    if udm is None:
        raise NoEncontrado("unidad de medida no encontrada")
    if udm.categoria_udm_id != udm_articulo.categoria_udm_id:
        raise ReglaNegocio(
            f"'{articulo.nombre}' se lleva en {udm_articulo.nombre}: la receta "
            f"no puede pedirlo en {udm.nombre}, que es de otra categoría de "
            "unidad de medida"
        )
    return udm


def _condicion_normalizada(valores: list[str] | None) -> frozenset[str]:
    """El orden en que se listan los valores no hace a la condición."""
    return frozenset(str(v) for v in (valores or []))


def editar_item(
    session: Session,
    item_id: uuid.UUID,
    *,
    cantidad: Decimal | None = None,
    expresion: str | None = None,
    merma_pct: Decimal | None = None,
    unidad_medida_id: uuid.UUID | None = None,
) -> RecetaItem:
    item = RecetaRepo(session).get_item(item_id)
    if item is None:
        raise NoEncontrado("ítem de receta no encontrado")
    articulo, udm_articulo = _articulo_y_udm(session, item.articulo_id)
    if unidad_medida_id is not None:
        udm = _udm_de_linea(session, unidad_medida_id, articulo, udm_articulo)
        item.unidad_medida_id = udm.id if udm is not udm_articulo else None
    if cantidad is not None or expresion is not None:
        # Se redondea con los decimales de **la unidad de la línea**, no con
        # los del artículo: quien teclea gramos espera que 24.4 sea 24, no
        # que se guarden tres decimales de un kilo (RN-UDM-005).
        udm = (
            session.get(UnidadMedida, item.unidad_medida_id)
            if item.unidad_medida_id
            else udm_articulo
        ) or udm_articulo
        item.cantidad, item.expresion = _resolver_cantidad(cantidad, expresion, udm)
    if merma_pct is not None:
        _validar_merma(merma_pct)
        item.merma_pct = merma_pct
    return item


def eliminar_item(session: Session, item_id: uuid.UUID) -> None:
    repo = RecetaRepo(session)
    item = repo.get_item(item_id)
    if item is None:
        raise NoEncontrado("ítem de receta no encontrado")
    repo.borrar_item(item)


def duplicar_receta(session: Session, receta_id: uuid.UUID) -> Receta:
    """Clona la receta y sus líneas con el sufijo "(copy)".

    No copia `articulo_id`: dos recetas produciendo el mismo artículo
    dejarían a `production` sin saber cuál explotar (RN-PRD). La copia nace
    suelta y se le asigna destino al guardarla.
    """
    original = _exigir(session, receta_id)
    repo = RecetaRepo(session)
    copia = repo.add(
        Receta(
            empresa_id=original.empresa_id,
            nombre=_nombre_libre(repo, original.nombre, original.empresa_id),
            rendimiento_cantidad=original.rendimiento_cantidad,
            rendimiento_unidad_medida_id=original.rendimiento_unidad_medida_id,
            flexible=original.flexible,
            criterio_ajuste=original.criterio_ajuste,
            articulo_id=None,
        )
    )
    for item in repo.items(receta_id):
        repo.add_item(
            RecetaItem(
                receta_id=copia.id,
                articulo_id=item.articulo_id,
                cantidad=item.cantidad,
                expresion=item.expresion,
                merma_pct=item.merma_pct,
            )
        )
    return copia


def eliminar_receta(session: Session, receta_id: uuid.UUID) -> None:
    """Borra la receta y sus líneas.

    Se niega si algún producto comercial la usa: borrarla dejaría al producto
    sin nada que descontar y la venta fallaría recién en caja. La consulta va
    por el contrato público de `sales` (no por su ORM) y nombra al producto,
    porque "violación de clave foránea" no le dice a nadie qué corregir.

    Lo que produce (`articulo_id`) no bloquea: el artículo sigue existiendo,
    solo se queda sin receta que lo fabrique.
    """
    receta = _exigir(session, receta_id)
    en_uso = productos_que_usan_receta(session, receta_id)
    if en_uso:
        raise Conflicto(
            f"'{receta.nombre}' la usan {len(en_uso)} producto(s): "
            f"{', '.join(en_uso[:3])}. Cámbiales la receta antes de borrarla"
        )
    repo = RecetaRepo(session)
    for item in repo.items(receta_id):
        repo.borrar_item(item)
    # El flush no es decorativo: sin `relationship` entre `receta` y
    # `receta_item`, SQLAlchemy no sabe que una depende de la otra y ordenaba
    # el DELETE de la cabecera **antes** que el de las líneas. Postgres lo
    # rechazaba por `fk_receta_item_receta_id_receta`, o sea que una receta
    # con insumos —todas— no se podía borrar: 500 en la cara del usuario. En
    # SQLite pasaba en verde porque el suite corría con las FK apagadas.
    session.flush()
    session.delete(receta)


def escalar_receta(
    session: Session, receta_id: uuid.UUID, factor: Decimal
) -> list[RecetaItem]:
    """Multiplica todas las cantidades por `factor` (Personal → Mediana).

    Cada línea se redondea con los decimales de SU unidad: 1.5 veces 3
    unidades de pan son 5 (no 4.5, que no existe), mientras que el queso en
    kilos sí admite el decimal. Por eso no se escala con una sola regla.
    """
    if factor <= 0:
        raise ReglaNegocio("el factor de escala debe ser > 0")
    _exigir(session, receta_id)
    repo = RecetaRepo(session)
    items = repo.items(receta_id)
    for item in items:
        _, udm = _articulo_y_udm(session, item.articulo_id)
        base = item.expresion or _texto(item.cantidad)
        item.cantidad = redondear(item.cantidad * factor, _decimales(udm))
        # La expresión acumula el escalado para que se vea de dónde salió el
        # número; si ya no entra en la columna, se pierde el rastro pero no
        # el valor.
        escalada = f"({base})*{_texto(factor)}"
        item.expresion = escalada if len(escalada) <= LARGO_EXPRESION else None
    return items


# --- Internos ---------------------------------------------------------------
def _articulo_producido(
    session: Session, receta: Receta, articulo_id: uuid.UUID
) -> uuid.UUID:
    """Liga la receta al artículo que produce (una subreceta: masa, salsa).

    Dos recetas produciendo el mismo artículo dejarían a `production` sin
    saber cuál explotar, así que la relación es exclusiva. Y un artículo no
    puede ser insumo de la receta que lo produce.
    """
    articulo = _exigir_articulo_de_la_empresa(session, articulo_id, receta.empresa_id)
    repo = RecetaRepo(session)
    # El choque se busca dentro de la empresa: la exclusividad es de su
    # catálogo, no del grupo.
    for otra in repo.list(receta.empresa_id):
        if otra.articulo_id == articulo_id and otra.id != receta.id:
            raise Conflicto(
                f"'{otra.nombre}' ya produce '{articulo.nombre}': un artículo lo "
                "produce una sola receta"
            )
    if any(i.articulo_id == articulo_id for i in repo.items(receta.id)):
        raise ReglaNegocio(
            f"'{articulo.nombre}' es insumo de esta receta: no puede ser "
            "también lo que produce"
        )
    return articulo_id


def _exigir(session: Session, receta_id: uuid.UUID) -> Receta:
    receta = RecetaRepo(session).get(receta_id)
    if receta is None:
        raise NoEncontrado("receta no encontrada")
    return receta


def _articulo_y_udm(
    session: Session, articulo_id: uuid.UUID
) -> tuple[Articulo, UnidadMedida]:
    articulo = ArticuloRepo(session).get(articulo_id)
    if articulo is None:
        raise NoEncontrado("artículo no encontrado")
    udm = session.get(UnidadMedida, articulo.unidad_medida_id)
    if udm is None:
        raise NoEncontrado("unidad de medida del artículo no encontrada")
    return articulo, udm


def _decimales(udm: UnidadMedida) -> int:
    return min(udm.decimales, DECIMALES_MAXIMOS)


def _resolver_cantidad(
    cantidad: Decimal | None, expresion: str | None, udm: UnidadMedida
) -> tuple[Decimal, str | None]:
    """La expresión manda: si viene, el resultado sale de evaluarla."""
    if expresion:
        valor, texto = evaluar(expresion), expresion.strip()
    elif cantidad is not None:
        valor, texto = cantidad, None
    else:
        raise ReglaNegocio("falta la cantidad (o la operación que la calcula)")
    valor = redondear(valor, _decimales(udm))
    if valor <= 0:
        raise ReglaNegocio(f"la cantidad debe ser > 0 (resultó {valor})")
    return valor, texto


def _validar_merma(merma_pct: Decimal) -> None:
    if merma_pct < 0 or merma_pct >= 100:
        raise ReglaNegocio("la merma debe estar entre 0 y 100 %")


def costo_linea(
    item: RecetaItem,
    articulo: Articulo,
    ratio_linea: Decimal | None = None,
    ratio_articulo: Decimal | None = None,
) -> Decimal:
    """La merma es insumo que entra y no llega al plato: se costea igual.

    Misma cuenta que descuenta el stock (`domain.rules.consumo_de_linea`), y
    a propósito: costear con una fórmula y descontar con otra es cómo el
    margen de un plato deja de cuadrar con lo que salió de la cámara, sin
    que ninguna de las dos parezca estar mal.

    Los ratios solo hacen falta si la línea eligió una unidad distinta a la
    del artículo (RN-UDM-005); sin ellos no se convierte nada, que es el
    caso de toda receta que hereda la unidad de su insumo.
    """
    cantidad = domain_rules.consumo_de_linea(
        item.cantidad, item.merma_pct, ratio_linea, ratio_articulo
    )
    return cantidad * articulo.costo_promedio


def ratios_de_linea(
    session: Session, item: RecetaItem, articulo: Articulo
) -> tuple[Decimal | None, Decimal | None]:
    """Los dos ratios que `costo_linea` necesita, o `(None, None)`.

    Devuelve `(None, None)` cuando la línea no eligió unidad: así quien
    costea no tiene que saber si hay conversión o no, y no paga dos
    consultas por línea cuando no la hay.
    """
    if not item.unidad_medida_id:
        return None, None
    udm_linea = session.get(UnidadMedida, item.unidad_medida_id)
    udm_articulo = session.get(UnidadMedida, articulo.unidad_medida_id)
    if udm_linea is None or udm_articulo is None:
        return None, None
    return udm_linea.ratio, udm_articulo.ratio


def _resumen(session: Session, receta: Receta) -> dict:
    udm = session.get(UnidadMedida, receta.rendimiento_unidad_medida_id)
    return {
        "id": receta.id,
        "empresa_id": receta.empresa_id,
        "nombre": receta.nombre,
        "rendimiento_cantidad": receta.rendimiento_cantidad,
        "rendimiento_unidad_medida_id": receta.rendimiento_unidad_medida_id,
        "rendimiento_unidad_medida_nombre": udm.nombre if udm else None,
        "articulo_id": receta.articulo_id,
        "flexible": receta.flexible,
        "criterio_ajuste": receta.criterio_ajuste,
    }


def _nombre_libre(repo: RecetaRepo, nombre: str, empresa_id: uuid.UUID) -> str:
    """"Pizza" → "Pizza (copy)" → "Pizza (copy) 2" → ...

    El sufijo no se apila: duplicar una copia da "Pizza (copy) 2", no
    "Pizza (copy) (copy)". El nombre es único **por empresa**
    (`crear_receta`), así que duplicar dos veces tiene que dar dos nombres
    distintos igual — y el choque solo se busca dentro de la misma empresa.
    """
    base = _SUFIJO_AL_FINAL.sub("", nombre).strip() or nombre
    candidato = f"{base} {SUFIJO_COPIA}"
    intento = 1
    while repo.get_by_nombre(candidato, empresa_id) is not None:
        intento += 1
        candidato = f"{base} {SUFIJO_COPIA} {intento}"
    return candidato


def _texto(valor: Decimal) -> str:
    """Sin ceros de relleno ni notación científica: "180" y "1.5", nunca
    "180.0000" ni "1.8E+2" —la expresión la lee una persona."""
    return format(valor.normalize(), "f")
