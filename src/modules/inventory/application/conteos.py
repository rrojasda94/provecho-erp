"""Casos de uso de conteo cíclico (RN-INV-007/014/015/021).

Cada categoría declara cada cuánto se cuenta lo que agrupa
(`categoria.frecuencia_conteo`) — no hay una periodicidad universal. El
calendario **no se almacena**: se deriva del último conteo cerrado más la
frecuencia de la categoría. Un programa persistido tendría que mantenerse
en sincronía con cada conteo, cada alta de categoría y cada alta de
almacén; derivarlo no puede desincronizarse.

El conteo nunca toca el stock: al cerrarse, cada diferencia genera un
`ajuste` pendiente, que sigue exigiendo un aprobador distinto del que
contó (RN-INV-006).
"""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import margenes
from src.modules.inventory.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import (
    Ajuste,
    Articulo,
    Categoria,
    Conteo,
    ConteoItem,
    Sku,
    Stock,
)
from src.modules.inventory.infrastructure.repositories import (
    AjusteRepo,
    ConteoRepo,
    StockRepo,
)
from src.modules.users.infrastructure.models import Almacen
from src.shared import fechas


def _hoy(hoy: datetime.date | None) -> datetime.date:
    """El día **del negocio**, no el del servidor: en Docker el proceso corre
    en UTC y un cierre de las 20:00 hora Perú caía al día siguiente, corriendo
    todo el calendario de conteos (`src/shared/fechas.py`)."""
    return hoy or fechas.hoy()


def _stock_de_categoria(
    session: Session, almacen_id: uuid.UUID, categoria_id: uuid.UUID | None
) -> list[Stock]:
    """Filas de stock del almacén, acotadas a la categoría si se indicó."""
    q = select(Stock).where(Stock.almacen_id == almacen_id)
    if categoria_id is not None:
        q = (
            q.join(Sku, Sku.id == Stock.sku_id)
            .join(Articulo, Articulo.id == Sku.articulo_id)
            .where(Articulo.categoria_id == categoria_id)
        )
    return list(session.scalars(q))


def abrir_conteo(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    categoria_id: uuid.UUID | None = None,
    tipo: str = "rutina",
    abierto_por: uuid.UUID,
    observacion: str | None = None,
    hoy: datetime.date | None = None,
    id: uuid.UUID | None = None,
) -> Conteo:
    """Abre el conteo y congela el stock esperado de cada SKU.

    El snapshot es del momento de abrir, no del de cerrar: el almacén sigue
    operando mientras se cuenta, y medir contra un stock que se movió
    durante el conteo inventa diferencias que nadie provocó.

    `id` explícito lo usa el hub que contó sin conexión (ADR-009): el conteo
    conserva su identidad al reproducirse en la nube.
    """
    if tipo not in rules.TIPOS_CONTEO:
        raise ReglaNegocio(f"tipo de conteo inválido: {tipo}")
    if categoria_id is not None and session.get(Categoria, categoria_id) is None:
        raise NoEncontrado("categoría no encontrada")

    repo = ConteoRepo(session)
    if id is not None and repo.get(id) is not None:
        # Reproducción idempotente del hub (ADR-009): reenviar el lote no
        # abre el conteo dos veces.
        return repo.get(id)
    if repo.abierto_en(almacen_id, categoria_id) is not None:
        raise Conflicto("ya hay un conteo abierto que cubre esa categoría")

    conteo = repo.add(
        Conteo(
            id=id or uuid.uuid4(),
            almacen_id=almacen_id,
            categoria_id=categoria_id,
            tipo=tipo,
            estado="abierto",
            fecha_programada=_fecha_programada(
                session, almacen_id, categoria_id
            ),
            abierto_por=abierto_por,
            observacion=observacion,
        )
    )
    for fila in _stock_de_categoria(session, almacen_id, categoria_id):
        repo.add_item(
            ConteoItem(
                conteo_id=conteo.id,
                sku_id=fila.sku_id,
                cantidad_sistema=fila.cantidad,
            )
        )
    return conteo


def _fecha_programada(
    session: Session, almacen_id: uuid.UUID, categoria_id: uuid.UUID | None
) -> datetime.date | None:
    """Fecha en que el programa exigía este conteo, para dejar registro de
    si llegó a tiempo. Un conteo general o de categoría sin frecuencia no
    responde a ningún programa."""
    if categoria_id is None:
        return None
    categoria = session.get(Categoria, categoria_id)
    if categoria is None or categoria.frecuencia_conteo is None:
        return None
    base, _ = _fecha_base(session, almacen_id, categoria)
    return rules.proxima_fecha_conteo(base, categoria.frecuencia_conteo)


def _fecha_base(
    session: Session,
    almacen_id: uuid.UUID,
    categoria: Categoria,
    hoy: datetime.date | None = None,
) -> tuple[datetime.date, Conteo | None]:
    """Desde cuándo se cuentan los días hasta el próximo conteo: el último
    conteo cerrado o, si nunca se contó, el alta de la categoría.

    `created_at` es `server_default`: una categoría recién insertada y aún
    sin refrescar lo tiene en None — ahí el reloj arranca hoy.
    """
    ultimo = ConteoRepo(session).ultimo_cerrado(almacen_id, categoria.id)
    if ultimo is not None and ultimo.cerrado_at is not None:
        return fechas.a_fecha_local(ultimo.cerrado_at), ultimo
    alta = fechas.a_fecha_local(categoria.created_at) or _hoy(hoy)
    return alta, None


def registrar_cantidades(
    session: Session,
    conteo_id: uuid.UUID,
    cantidades: list[tuple[uuid.UUID, Decimal]],
) -> Conteo:
    """Anota lo contado. Un SKU fuera del snapshot se agrega con sistema en
    0: encontrar en el almacén algo que el ERP no registra es exactamente
    el sobrante que el conteo existe para detectar."""
    repo = ConteoRepo(session)
    conteo = repo.get(conteo_id)
    if conteo is None:
        raise NoEncontrado("conteo no encontrado")
    if conteo.estado != "abierto":
        raise ReglaNegocio(f"el conteo ya está {conteo.estado}")

    for sku_id, cantidad in cantidades:
        if cantidad < 0:
            raise ReglaNegocio("la cantidad contada no puede ser negativa")
        item = repo.item(conteo_id, sku_id)
        if item is None:
            if session.get(Sku, sku_id) is None:
                raise NoEncontrado("SKU no encontrado")
            fila = StockRepo(session).get(conteo.almacen_id, sku_id)
            item = repo.add_item(
                ConteoItem(
                    conteo_id=conteo_id,
                    sku_id=sku_id,
                    cantidad_sistema=fila.cantidad if fila else Decimal(0),
                )
            )
        item.cantidad_contada = cantidad
    return conteo


def cerrar_conteo(
    session: Session,
    conteo_id: uuid.UUID,
    cerrado_por: uuid.UUID,
) -> tuple[Conteo, list[Ajuste]]:
    """Cierra el conteo y solicita un ajuste por cada diferencia.

    Los ítems que nadie contó se ignoran: un conteo parcial no puede
    declarar faltante lo que no se miró. Cada ajuste nace `pendiente` — el
    que contó no lo aprueba (RN-INV-006).
    """
    repo = ConteoRepo(session)
    conteo = repo.get(conteo_id)
    if conteo is None:
        raise NoEncontrado("conteo no encontrado")
    if conteo.estado != "abierto":
        raise ReglaNegocio(f"el conteo ya está {conteo.estado}")

    almacen = session.get(Almacen, conteo.almacen_id)
    margen, piso = margenes.margen_de_empresa(session, almacen.empresa_id)
    items = repo.items(conteo_id)
    costos = margenes.costos_por_sku(session, [i.sku_id for i in items])
    ajuste_repo = AjusteRepo(session)
    generados: list[Ajuste] = []
    for item in items:
        diferencia = item.diferencia
        if diferencia is None or diferencia == 0:
            continue
        costo = costos.get(item.sku_id, Decimal(0))
        generados.append(
            ajuste_repo.add(
                Ajuste(
                    almacen_id=conteo.almacen_id,
                    sku_id=item.sku_id,
                    cantidad=diferencia,
                    motivo=rules.motivo_por_diferencia(diferencia),
                    conteo_id=conteo.id,
                    solicitado_por=cerrado_por,
                    dentro_margen=rules.diferencia_dentro_margen(
                        item.cantidad_sistema,
                        diferencia,
                        margen,
                        valor_diferencia=diferencia * costo,
                        piso=piso,
                    ),
                    estado="pendiente",
                )
            )
        )

    conteo.estado = "cerrado"
    conteo.cerrado_por = cerrado_por
    conteo.cerrado_at = datetime.datetime.now(datetime.UTC)
    return conteo, generados


def anular_conteo(
    session: Session,
    conteo_id: uuid.UUID,
    anulado_por: uuid.UUID,
    motivo: str,
) -> Conteo:
    """Cierra sin ajustes un conteo abierto por error.

    Existe porque sin esto la única salida era cerrarlo vacío, y un conteo
    cerrado en cero dice "se contó y no había diferencias" —lo contrario de
    lo que pasó— además de poner al día el calendario de una categoría que
    nadie contó. El motivo es obligatorio: anular es la forma de hacer
    desaparecer un conteo incómodo, así que tiene que quedar dicho por qué.
    """
    repo = ConteoRepo(session)
    conteo = repo.get(conteo_id)
    if conteo is None:
        raise NoEncontrado("conteo no encontrado")
    if conteo.estado != "abierto":
        raise ReglaNegocio(f"el conteo ya está {conteo.estado}")
    if not motivo.strip():
        raise ReglaNegocio("anular un conteo exige motivo")

    conteo.estado = "anulado"
    conteo.cerrado_por = anulado_por
    conteo.cerrado_at = datetime.datetime.now(datetime.UTC)
    conteo.observacion = motivo.strip()
    return conteo


def programa(
    session: Session,
    *,
    almacen_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    hoy: datetime.date | None = None,
) -> list[dict]:
    """Calendario derivado: qué categoría toca contar en qué almacén.

    Solo entran las categorías con frecuencia configurada — el resto está
    deliberadamente fuera del ciclo.
    """
    hoy = _hoy(hoy)
    almacenes = select(Almacen).where(Almacen.deleted_at.is_(None))
    if almacen_id is not None:
        almacenes = almacenes.where(Almacen.id == almacen_id)
    if empresa_id is not None:
        almacenes = almacenes.where(Almacen.empresa_id == empresa_id)

    filas = []
    for almacen in session.scalars(almacenes):
        categorias = select(Categoria).where(
            Categoria.deleted_at.is_(None),
            Categoria.empresa_id == almacen.empresa_id,
            Categoria.frecuencia_conteo.is_not(None),
        )
        for categoria in session.scalars(categorias):
            base, ultimo = _fecha_base(session, almacen.id, categoria, hoy)
            proxima = rules.proxima_fecha_conteo(base, categoria.frecuencia_conteo)
            estado, atraso = rules.estado_programa_conteo(proxima, hoy)
            filas.append(
                {
                    "almacen_id": almacen.id,
                    "categoria_id": categoria.id,
                    "categoria": categoria.nombre,
                    "frecuencia": categoria.frecuencia_conteo,
                    "ultimo_conteo": fechas.a_fecha_local(
                        ultimo.cerrado_at if ultimo else None
                    ),
                    "proxima_fecha": proxima,
                    "estado": estado,
                    "dias_atraso": atraso,
                }
            )
    return sorted(filas, key=lambda f: (-f["dias_atraso"], f["categoria"]))


def reportar_vencidos(
    session: Session,
    *,
    almacen_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    hoy: datetime.date | None = None,
) -> list[dict]:
    """Reporta a almacén y gerencia los conteos que no se hicieron en su
    fecha (RN-INV-021). Publica `inventory.conteo_vencido` por cada uno.

    Lo dispara `inventory.reportar_conteos_vencidos` (Celery beat, diario
    06:15 hora Perú) y también el endpoint, a demanda. Diario y no más
    seguido porque el dato cambia una vez por día: el calendario se deriva
    de fechas, no de horas.
    """
    vencidos = [
        fila
        for fila in programa(
            session, almacen_id=almacen_id, empresa_id=empresa_id, hoy=hoy
        )
        if fila["estado"] == "vencido"
    ]
    for fila in vencidos:
        event_bus.publish(
            "inventory.conteo_vencido",
            {
                "almacen_id": str(fila["almacen_id"]),
                "categoria_id": str(fila["categoria_id"]),
                "categoria": fila["categoria"],
                "frecuencia": fila["frecuencia"],
                "fecha_programada": fila["proxima_fecha"].isoformat(),
                "dias_atraso": fila["dias_atraso"],
                # El reporte va a las dos áreas: quien debía contar y quien
                # responde por que se cuente.
                "dirigido_a": ["almacen", "gerencia"],
            },
        )
    return vencidos


def detalle(session: Session, conteo_id: uuid.UUID) -> tuple[Conteo, list[ConteoItem]]:
    repo = ConteoRepo(session)
    conteo = repo.get(conteo_id)
    if conteo is None:
        raise NoEncontrado("conteo no encontrado")
    return conteo, repo.items(conteo_id)
