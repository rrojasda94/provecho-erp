"""Casos de uso de receta: la ficha técnica de lo que se produce y se vende.

Una receta es el BOM de un producto comercial (`producto_comercial.receta_id`)
o de una subreceta (`receta.articulo_id`). Acá vive su CRUD, el duplicado
para partir de una existente y el escalado por factor.

Dos decisiones que se repiten en todo el archivo:

- **La unidad la pone el insumo.** La cantidad de cada línea se expresa en
  la UdM del artículo y se redondea a los decimales de esa unidad
  (RN-GER-010). No hay campo de unidad en la línea: sería un segundo lugar
  donde el dato puede quedar distinto del que usa el descuento de stock.
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
    nombre: str,
    rendimiento_cantidad: Decimal,
    rendimiento_unidad_medida_id: uuid.UUID,
    articulo_id: uuid.UUID | None = None,
    flexible: bool = False,
    criterio_ajuste: str | None = None,
) -> Receta:
    nombre = a_titulo(nombre)
    repo = RecetaRepo(session)
    if repo.get_by_nombre(nombre):
        raise Conflicto(f"ya existe una receta '{nombre}'")
    if session.get(UnidadMedida, rendimiento_unidad_medida_id) is None:
        raise NoEncontrado("unidad de medida no encontrada")
    if articulo_id is not None and session.get(Articulo, articulo_id) is None:
        raise NoEncontrado("artículo no encontrado")
    if rendimiento_cantidad <= 0:
        raise ReglaNegocio("el rendimiento debe ser > 0")
    return repo.add(
        Receta(
            nombre=nombre,
            rendimiento_cantidad=rendimiento_cantidad,
            rendimiento_unidad_medida_id=rendimiento_unidad_medida_id,
            articulo_id=articulo_id,
            flexible=flexible,
            criterio_ajuste=criterio_ajuste,
        )
    )


def editar_receta(session: Session, receta_id: uuid.UUID, **campos) -> Receta:
    receta = _exigir(session, receta_id)
    if campos.get("nombre") is not None:
        nombre = a_titulo(campos["nombre"])
        otra = RecetaRepo(session).get_by_nombre(nombre)
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


def listar_recetas(session: Session) -> list[dict]:
    return [_resumen(session, r) for r in RecetaRepo(session).list()]


def detalle_receta(session: Session, receta_id: uuid.UUID) -> dict:
    """La receta con sus líneas ya resueltas: nombre del insumo, su unidad,
    los decimales con los que se teclea y el costo que aporta la línea."""
    receta = _exigir(session, receta_id)
    repo = RecetaRepo(session)
    items = repo.items(receta_id)
    lineas, costo = [], Decimal(0)
    for item in items:
        articulo, udm = _articulo_y_udm(session, item.articulo_id)
        costo_linea_valor = costo_linea(item, articulo)
        costo += costo_linea_valor
        lineas.append(
            {
                "id": item.id,
                "articulo_id": articulo.id,
                "articulo_nombre": articulo.nombre,
                "unidad_medida_id": udm.id,
                "unidad_medida_nombre": udm.nombre,
                "decimales": _decimales(udm),
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
) -> RecetaItem:
    receta = _exigir(session, receta_id)
    articulo, udm = _articulo_y_udm(session, articulo_id)
    if receta.articulo_id is not None and receta.articulo_id == articulo_id:
        raise ReglaNegocio(
            f"'{articulo.nombre}' es lo que la receta produce: no puede ser "
            "también su insumo"
        )
    repo = RecetaRepo(session)
    if any(i.articulo_id == articulo_id for i in repo.items(receta_id)):
        raise Conflicto(f"'{articulo.nombre}' ya está en la receta")
    valor, texto = _resolver_cantidad(cantidad, expresion, udm)
    _validar_merma(merma_pct)
    return repo.add_item(
        RecetaItem(
            receta_id=receta_id,
            articulo_id=articulo_id,
            cantidad=valor,
            expresion=texto,
            merma_pct=merma_pct,
        )
    )


def editar_item(
    session: Session,
    item_id: uuid.UUID,
    *,
    cantidad: Decimal | None = None,
    expresion: str | None = None,
    merma_pct: Decimal | None = None,
) -> RecetaItem:
    item = RecetaRepo(session).get_item(item_id)
    if item is None:
        raise NoEncontrado("ítem de receta no encontrado")
    if cantidad is not None or expresion is not None:
        _, udm = _articulo_y_udm(session, item.articulo_id)
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
            nombre=_nombre_libre(repo, original.nombre),
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
    articulo, _ = _articulo_y_udm(session, articulo_id)
    repo = RecetaRepo(session)
    for otra in repo.list():
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


def costo_linea(item: RecetaItem, articulo: Articulo) -> Decimal:
    """La merma es insumo que entra y no llega al plato: se costea igual."""
    factor = Decimal(1) + (item.merma_pct / Decimal(100))
    return item.cantidad * factor * articulo.costo_promedio


def _resumen(session: Session, receta: Receta) -> dict:
    udm = session.get(UnidadMedida, receta.rendimiento_unidad_medida_id)
    return {
        "id": receta.id,
        "nombre": receta.nombre,
        "rendimiento_cantidad": receta.rendimiento_cantidad,
        "rendimiento_unidad_medida_id": receta.rendimiento_unidad_medida_id,
        "rendimiento_unidad_medida_nombre": udm.nombre if udm else None,
        "articulo_id": receta.articulo_id,
        "flexible": receta.flexible,
        "criterio_ajuste": receta.criterio_ajuste,
    }


def _nombre_libre(repo: RecetaRepo, nombre: str) -> str:
    """"Pizza" → "Pizza (copy)" → "Pizza (copy) 2" → ...

    El sufijo no se apila: duplicar una copia da "Pizza (copy) 2", no
    "Pizza (copy) (copy)". El nombre es único (`crear_receta`), así que
    duplicar dos veces tiene que dar dos nombres distintos igual.
    """
    base = _SUFIJO_AL_FINAL.sub("", nombre).strip() or nombre
    candidato = f"{base} {SUFIJO_COPIA}"
    intento = 1
    while repo.get_by_nombre(candidato) is not None:
        intento += 1
        candidato = f"{base} {SUFIJO_COPIA} {intento}"
    return candidato


def _texto(valor: Decimal) -> str:
    """Sin ceros de relleno ni notación científica: "180" y "1.5", nunca
    "180.0000" ni "1.8E+2" —la expresión la lee una persona."""
    return format(valor.normalize(), "f")
