"""El recetario como una hoja de cálculo: insumos en las filas, recetas en las
columnas, gramajes en las celdas (ADR-057).

El editor de a una receta funciona y no alcanza. Corregir el queso de las tres
presentaciones de ocho pizzas son veinticuatro fichas abiertas de a una, y
comparar dos recetas obliga a recordar la primera mientras se mira la segunda.
Puesto en grilla, el trabajo que hoy son veinticuatro pantallas es una columna
y una mirada.

Dos operaciones y nada más:

- `grilla` devuelve el rectángulo entero en **una consulta por tabla**. La
  alternativa era `detalle_receta` por receta, que es exactamente el N+1 que
  hace inusable el lienzo hoy.
- `guardar` recibe las celdas que cambiaron y las resuelve contra
  `agregar_item` / `editar_item` / `eliminar_item`. **No inserta directo**:
  esas funciones son las que saben de la unidad, de la merma, de la
  aritmética tecleada (RN-COM-024) y de qué condición hace distinta a una
  línea. Un guardado con su propia lógica sería un segundo juego de reglas
  que se separa del primero a la primera corrección.

**La identidad de una celda es `(receta, insumo, condición)`**, no un id de
línea. Es lo que permite pegar un rectángulo desde Excel —donde no hay ids—
sin que el cliente tenga que resolver a qué línea corresponde cada valor. La
condición entra en la clave porque desde ADR-056 el mismo insumo puede estar
dos veces en la misma receta si cada línea aplica a otra combinación.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.application import recetas as recetas_uc
from src.modules.inventory.application.errors import AppError, NoEncontrado
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Receta,
    RecetaItem,
    UnidadMedida,
)

MAXIMO_CELDAS = 2000
"""Tope por guardado. Un rectángulo real —cuarenta insumos por veinte
recetas— no llega ni cerca; el límite está para que pegar una hoja entera por
accidente no se convierta en una transacción de diez minutos."""


def _clave(receta_id, articulo_id, aplica_valores) -> tuple:
    """La identidad de una celda. El orden de los valores de la condición no
    la cambia: es un conjunto, no una lista."""
    return (
        str(receta_id),
        str(articulo_id),
        frozenset(str(v) for v in (aplica_valores or [])),
    )


def grilla(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    receta_ids: Sequence[uuid.UUID] | None = None,
) -> dict:
    """El rectángulo: qué recetas, qué insumos y qué hay en cada cruce.

    Sin `receta_ids` devuelve el recetario entero de la empresa. Es lo que
    quiere quien abre la pantalla para buscar; filtrar es lo que quiere quien
    ya sabe qué comparar.
    """
    consulta = select(Receta).where(Receta.empresa_id == empresa_id)
    if receta_ids:
        consulta = consulta.where(Receta.id.in_(list(receta_ids)))
    recetas = list(session.scalars(consulta.order_by(Receta.nombre)))
    if not recetas:
        return {"recetas": [], "insumos": [], "celdas": []}

    items = list(
        session.scalars(
            select(RecetaItem)
            .where(RecetaItem.receta_id.in_([r.id for r in recetas]))
            .order_by(RecetaItem.orden)
        )
    )
    articulos = {
        a.id: a
        for a in session.scalars(
            select(Articulo).where(
                Articulo.id.in_({i.articulo_id for i in items} or {uuid.uuid4()})
            )
        )
    }
    udms = {u.id: u for u in session.scalars(select(UnidadMedida))}

    def unidad_de(item: RecetaItem) -> UnidadMedida | None:
        if item.unidad_medida_id:
            return udms.get(item.unidad_medida_id)
        articulo = articulos.get(item.articulo_id)
        return udms.get(articulo.unidad_medida_id) if articulo else None

    return {
        "recetas": [
            {
                "id": r.id,
                "nombre": r.nombre,
                "rendimiento_cantidad": r.rendimiento_cantidad,
                "rendimiento_unidad_medida_id": r.rendimiento_unidad_medida_id,
                "es_kit": r.es_kit,
            }
            for r in recetas
        ],
        # Solo los insumos que alguna de estas recetas usa: una grilla con las
        # cuatrocientas filas del catálogo es una grilla vacía.
        "insumos": [
            {
                "articulo_id": a.id,
                "nombre": a.nombre,
                "unidad_medida_id": a.unidad_medida_id,
                "unidad": udms[a.unidad_medida_id].nombre
                if a.unidad_medida_id in udms
                else "",
                "decimales": _decimales(udms.get(a.unidad_medida_id)),
                "costo_promedio": a.costo_promedio,
            }
            for a in sorted(articulos.values(), key=lambda a: a.nombre)
        ],
        "celdas": [
            {
                "item_id": i.id,
                "receta_id": i.receta_id,
                "articulo_id": i.articulo_id,
                "cantidad": i.cantidad,
                # Lo tecleado gana sobre el número al mostrar: quien escribió
                # "450/3" quiere volver a ver la división, no 150 (RN-COM-024).
                "expresion": i.expresion,
                "merma_pct": i.merma_pct,
                "unidad_medida_id": i.unidad_medida_id,
                "unidad": unidad.nombre if (unidad := unidad_de(i)) else "",
                "decimales": _decimales(unidad),
                "aplica_valores": i.aplica_valores or [],
                "orden": i.orden,
            }
            for i in items
        ],
    }


def _decimales(udm: UnidadMedida | None) -> int:
    if udm is None:
        return recetas_uc.DECIMALES_MAXIMOS
    return min(udm.decimales, recetas_uc.DECIMALES_MAXIMOS)


def guardar(
    session: Session, *, empresa_id: uuid.UUID, celdas: Sequence[dict]
) -> dict:
    """Aplica las celdas que cambiaron. Devuelve qué pasó con cada una.

    Una celda **sin cantidad** borra la línea: en una grilla, vaciar la celda
    es la forma natural de decir "este insumo no va en esta receta", y pedir
    un botón aparte para eso sería inventar un gesto que nadie busca.

    **Una celda que falla no arrastra a las demás.** Cada una entra en su
    propio `SAVEPOINT`, igual que cada receta en la carga masiva (ADR-046):
    pegar cuarenta celdas y perderlas todas porque una tenía un insumo mal
    escrito es el modo de falla que hace que nadie vuelva a pegar nada.
    """
    if len(celdas) > MAXIMO_CELDAS:
        raise AppError(
            f"demasiadas celdas de una vez ({len(celdas)}, máximo "
            f"{MAXIMO_CELDAS}): guardá por partes"
        )
    recetas = {
        r.id: r
        for r in session.scalars(
            select(Receta).where(Receta.empresa_id == empresa_id)
        )
    }
    existentes = {}
    if recetas:
        for item in session.scalars(
            select(RecetaItem).where(RecetaItem.receta_id.in_(list(recetas)))
        ):
            existentes[_clave(item.receta_id, item.articulo_id, item.aplica_valores)] = item

    resultados = []
    for celda in celdas:
        try:
            with session.begin_nested():
                resultados.append(_aplicar(session, celda, recetas, existentes))
        except AppError as e:
            resultados.append(
                {
                    "receta_id": celda.get("receta_id"),
                    "articulo_id": celda.get("articulo_id"),
                    "accion": "problema",
                    "detalle": str(e),
                }
            )
    return {
        "resultados": resultados,
        "aplicadas": sum(1 for r in resultados if r["accion"] != "problema"),
        "con_problema": sum(1 for r in resultados if r["accion"] == "problema"),
    }


def _aplicar(session: Session, celda: dict, recetas: dict, existentes: dict) -> dict:
    receta_id = uuid.UUID(str(celda["receta_id"]))
    articulo_id = uuid.UUID(str(celda["articulo_id"]))
    if receta_id not in recetas:
        raise NoEncontrado("receta no encontrada en esta empresa")
    condicion = celda.get("aplica_valores") or []
    clave = _clave(receta_id, articulo_id, condicion)
    item = existentes.get(clave)
    expresion = (celda.get("expresion") or "").strip()
    base = {"receta_id": receta_id, "articulo_id": articulo_id}

    if not expresion:
        if item is None:
            # Vaciar una celda que ya estaba vacía no es un error ni un
            # cambio: es lo que pasa al pegar un rectángulo con huecos.
            return {**base, "accion": "sin_cambio"}
        recetas_uc.eliminar_item(session, item.id)
        existentes.pop(clave, None)
        return {**base, "accion": "borrada"}

    unidad = celda.get("unidad_medida_id")
    merma = Decimal(str(celda.get("merma_pct") or 0))
    if item is None:
        nuevo = recetas_uc.agregar_item(
            session,
            receta_id,
            articulo_id=articulo_id,
            expresion=expresion,
            merma_pct=merma,
            unidad_medida_id=uuid.UUID(str(unidad)) if unidad else None,
            aplica_valores=[str(v) for v in condicion] or None,
            orden=int(celda.get("orden") or 0),
        )
        existentes[clave] = nuevo
        return {**base, "accion": "creada", "item_id": nuevo.id, "cantidad": nuevo.cantidad}

    recetas_uc.editar_item(
        session,
        item.id,
        expresion=expresion,
        merma_pct=merma,
        unidad_medida_id=uuid.UUID(str(unidad)) if unidad else None,
    )
    return {**base, "accion": "actualizada", "item_id": item.id, "cantidad": item.cantidad}
