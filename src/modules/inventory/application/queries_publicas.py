"""Contrato público de lectura de `inventory` para otros módulos.

Mismo criterio que `sales.application.queries_publicas`: único punto de
entrada para que otro módulo lea datos de `inventory`, devolviendo DTOs
(dicts), nunca el ORM. Nadie importa `inventory.infrastructure` desde afuera.
"""

import datetime
import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.inventory.application import recetas as recetas_uc
from src.modules.inventory.infrastructure.models import (
    Articulo,
    IncidenciaInventario,
    MovimientoInventario,
    Receta,
    RecetaItem,
    ReservaStock,
    Sku,
    SolicitudInsumos,
    SolicitudItem,
    Stock,
    UnidadMedida,
)
from src.modules.users.infrastructure.models import Almacen
from src.shared import fechas


def unidad_medida_para_magnitud(session: Session, udm_id: uuid.UUID) -> dict | None:
    """Nombre y decimales de una UdM, para expresar una cantidad con su
    unidad (RN-GER-010). `None` si no existe."""
    udm = session.scalar(select(UnidadMedida).where(UnidadMedida.id == udm_id))
    if udm is None:
        return None
    return {"id": udm.id, "nombre": udm.nombre, "decimales": udm.decimales}


def receta_resumen(session: Session, receta_id: uuid.UUID) -> dict | None:
    """Nombre y rendimiento de una receta, para que `sales` valide que la
    que le asignan a un producto comercial existe sin importar su ORM.
    `None` si no existe."""
    receta = session.scalar(select(Receta).where(Receta.id == receta_id))
    if receta is None:
        return None
    return {
        "id": receta.id,
        "nombre": receta.nombre,
        "rendimiento_cantidad": receta.rendimiento_cantidad,
        "rendimiento_unidad_medida_id": receta.rendimiento_unidad_medida_id,
        "articulo_id": receta.articulo_id,
    }


def insumos_de_receta(session: Session, receta_id: uuid.UUID) -> list[dict]:
    """Qué artículos usa una receta, con su nombre. `articulo_id` → nombre.

    Es lo que `sales` necesita para las restas ("sin cebolla", RN-PRD-004):
    la lista de lo que se puede quitar de un plato **es** la lista de
    insumos de su receta, así que no hay nada que configurar aparte — una
    tabla de "quitables" sería la misma información escrita dos veces, y
    dos datos que dicen lo mismo terminan diciendo cosas distintas.

    Devuelve el nombre además del id porque el KDS tiene que imprimir "SIN
    CEBOLLA" y `sales` no puede leer `articulo` por su cuenta.
    """
    filas = session.execute(
        select(Articulo.id, Articulo.nombre)
        .join(RecetaItem, RecetaItem.articulo_id == Articulo.id)
        .where(RecetaItem.receta_id == receta_id)
        .order_by(Articulo.nombre)
    )
    return [{"articulo_id": fila.id, "nombre": fila.nombre} for fila in filas]


def nombres_de_articulos(
    session: Session, articulo_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """`articulo_id` → nombre, para módulos que guardan ids de artículo y
    tienen que imprimirlos (el KDS y su "SIN CEBOLLA"). Los ids que no
    existen sencillamente no aparecen: quien los muestre decide qué poner en
    su lugar."""
    if not articulo_ids:
        return {}
    filas = session.execute(
        select(Articulo.id, Articulo.nombre).where(
            Articulo.id.in_(list(articulo_ids))
        )
    )
    return {fila.id: fila.nombre for fila in filas}


def costo_unitario_de_recetas(
    session: Session, receta_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    """`receta_id` → costo de **una unidad** de rendimiento.

    Lo usa quien calcula margen sin conocer el modelo de recetas: la receta
    rinde N porciones, así que el costo de la porción es el de la receta
    dividido por su rendimiento. Reusa `recetas._costo_linea`, que ya
    contempla la merma (insumo que entra y no llega al plato), en vez de
    recalcular el costo con otro criterio y que dos pantallas del ERP
    muestren números distintos para lo mismo.

    Una receta sin rendimiento válido no entra en el resultado — nunca se
    devuelve costo cero, que se leería como "gratis" en vez de
    "desconocido".
    """
    if not receta_ids:
        return {}
    recetas = list(
        session.scalars(select(Receta).where(Receta.id.in_(list(receta_ids))))
    )
    costos: dict[uuid.UUID, Decimal] = {}
    for receta in recetas:
        if not receta.rendimiento_cantidad or receta.rendimiento_cantidad <= 0:
            continue
        items = list(
            session.scalars(
                select(RecetaItem).where(RecetaItem.receta_id == receta.id)
            )
        )
        if not items:
            continue
        total = Decimal(0)
        for item in items:
            articulo = session.get(Articulo, item.articulo_id)
            if articulo is None:
                continue
            ratio_linea, ratio_articulo = recetas_uc.ratios_de_linea(
                session, item, articulo
            )
            total += recetas_uc.costo_linea(
                item, articulo, ratio_linea, ratio_articulo
            )
        costos[receta.id] = total / receta.rendimiento_cantidad
    return costos


def solicitudes_resumen_para_negociacion(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
    limit: int = 50,
) -> list[dict]:
    """Qué artículos pide más cada sucursal (RN-DOC-005), para que
    `purchases` negocie volumen con proveedores sin importar el dominio de
    `inventory`. Suma `cantidad_solicitada` por artículo y sucursal —lo
    pedido, no lo aprobado ni lo despachado: es la demanda real, incluso la
    que el central no llegó a cubrir— y descarta las solicitudes canceladas,
    que nunca representaron una necesidad real, y los borradores, que todavía
    no se pidieron: negociar volumen con una lista a medio llenar sería
    prometerle al proveedor demanda que nadie confirmó (RN-INV-023).

    `sucursal_id` es `None` para almacenes sin sucursal (central, producción):
    su demanda cuenta igual, solo no se puede atribuir a un local.
    `empresa_id=None` = sin filtro: solo un superusuario sin empresa asignada
    (`Tenant.filtro_empresa`)."""
    stmt = (
        select(
            Articulo.id.label("articulo_id"),
            Articulo.nombre.label("articulo_nombre"),
            Almacen.sucursal_id,
            func.sum(SolicitudItem.cantidad_solicitada).label("cantidad_total"),
            func.count(func.distinct(SolicitudInsumos.id)).label("num_solicitudes"),
        )
        .select_from(SolicitudItem)
        .join(SolicitudInsumos, SolicitudInsumos.id == SolicitudItem.solicitud_id)
        .join(Almacen, Almacen.id == SolicitudInsumos.almacen_solicitante_id)
        .join(Sku, Sku.id == SolicitudItem.sku_id)
        .join(Articulo, Articulo.id == Sku.articulo_id)
        .where(SolicitudInsumos.estado.not_in(("cancelada", "borrador")))
        .group_by(Articulo.id, Articulo.nombre, Almacen.sucursal_id)
        .order_by(func.sum(SolicitudItem.cantidad_solicitada).desc())
        .limit(limit)
    )
    if empresa_id is not None:
        stmt = stmt.where(Almacen.empresa_id == empresa_id)
    if desde is not None:
        stmt = stmt.where(SolicitudInsumos.created_at >= fechas.inicio_dia_utc(desde))
    if hasta is not None:
        stmt = stmt.where(SolicitudInsumos.created_at <= fechas.fin_dia_utc(hasta))

    return [
        {
            "articulo_id": fila.articulo_id,
            "articulo_nombre": fila.articulo_nombre,
            "sucursal_id": fila.sucursal_id,
            "cantidad_total": fila.cantidad_total,
            "num_solicitudes": fila.num_solicitudes,
        }
        for fila in session.execute(stmt)
    ]


# --- Excepciones: lo que el sistema hizo (o dejó de hacer) en silencio ------
# Las tres consultas de abajo existen por la misma razón: hay decisiones que
# el ERP toma correctamente sin frenar la operación —no descontar, dejar el
# disponible negativo, sacar sin lote— y que hasta ahora no tenían dónde
# verse. Una excepción que nadie mira deja de ser una excepción.

MOTIVO_INCIDENCIA = {
    "sin_almacen": "Sucursal sin almacén",
    "sin_sku": "Artículo sin SKU activo",
    "stock_insuficiente": "Stock teórico insuficiente",
}


def consumos_omitidos(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
    limite: int = 50,
) -> list[dict]:
    """Movimientos que no se hicieron y por qué (`incidencia_inventario`).

    Cada fila es stock que quedó distinto de la realidad sin que nadie lo
    haya pedido. El motivo es lo accionable: dice si hay que configurar la
    sucursal, dar de alta un SKU, o mirar por qué el stock ya venía mal.
    """
    stmt = (
        select(IncidenciaInventario, Articulo.nombre)
        .outerjoin(Articulo, Articulo.id == IncidenciaInventario.articulo_id)
        .order_by(IncidenciaInventario.created_at.desc())
        .limit(limite)
    )
    if empresa_id is not None:
        stmt = stmt.where(IncidenciaInventario.empresa_id == empresa_id)
    if desde is not None:
        stmt = stmt.where(
            IncidenciaInventario.created_at >= fechas.inicio_dia_utc(desde)
        )
    if hasta is not None:
        stmt = stmt.where(IncidenciaInventario.created_at <= fechas.fin_dia_utc(hasta))

    return [
        {
            "fecha": fechas.a_fecha_local(incidencia.created_at),
            "origen": incidencia.origen,
            "referencia": incidencia.referencia,
            "motivo": MOTIVO_INCIDENCIA.get(incidencia.tipo, incidencia.tipo),
            # El id ancla el enlace de la fila (ADR-036): sin él, la lista de
            # problemas dice qué pasó y no a dónde ir a resolverlo.
            "articulo_id": incidencia.articulo_id,
            "articulo": nombre or "—",
            "cantidad": incidencia.cantidad,
            "detalle": incidencia.detalle,
        }
        for incidencia, nombre in session.execute(stmt)
    ]


def disponible_negativo(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    limite: int = 50,
) -> list[dict]:
    """SKUs comprometidos por encima de lo que hay físicamente (RN-INV-009).

    Es un estado alcanzable a propósito: reservar exige disponible, pero
    consumir no se bloquea nunca —una venta ya ocurrida no se niega—, así
    que una reserva puede quedar sin respaldo. Cada fila es una promesa que
    el almacén no puede cumplir hoy.

    Foto del presente: el rango de fechas del tablero no aplica.
    """
    reservas = (
        select(
            ReservaStock.almacen_id,
            ReservaStock.sku_id,
            func.sum(ReservaStock.cantidad).label("reservado"),
        )
        .where(ReservaStock.estado == "activa")
        .group_by(ReservaStock.almacen_id, ReservaStock.sku_id)
        .subquery()
    )
    stmt = (
        select(
            Stock.sku_id,
            Almacen.nombre.label("almacen"),
            Articulo.nombre.label("articulo"),
            Stock.cantidad,
            reservas.c.reservado,
        )
        .select_from(Stock)
        .join(
            reservas,
            (reservas.c.almacen_id == Stock.almacen_id)
            & (reservas.c.sku_id == Stock.sku_id),
        )
        .join(Almacen, Almacen.id == Stock.almacen_id)
        .join(Sku, Sku.id == Stock.sku_id)
        .join(Articulo, Articulo.id == Sku.articulo_id)
        .where(reservas.c.reservado > Stock.cantidad)
        .order_by((Stock.cantidad - reservas.c.reservado).asc())
        .limit(limite)
    )
    if empresa_id is not None:
        stmt = stmt.where(Almacen.empresa_id == empresa_id)

    return [
        {
            "sku_id": fila.sku_id,
            "almacen": fila.almacen,
            "articulo": fila.articulo,
            "cantidad": fila.cantidad,
            "reservado": fila.reservado,
            "disponible": fila.cantidad - fila.reservado,
        }
        for fila in session.execute(stmt)
    ]


def salidas_sin_lote(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
    limite: int = 50,
) -> list[dict]:
    """Salidas de artículos con control de lote que ningún lote respalda.

    Pasa cuando el total alcanza pero el reparto FEFO no encuentra de dónde
    tomarlo: stock cargado antes de activar el control de lote, o el resto
    bloqueado por vencimiento. Es deliberado (ADR-015) —la operación ya
    ocurrió y no se frena— y rompe la trazabilidad de ese movimiento, que es
    justo lo que el control de lote existe para dar.
    """
    stmt = (
        select(
            MovimientoInventario.ts,
            MovimientoInventario.sku_id,
            Almacen.nombre.label("almacen"),
            Articulo.nombre.label("articulo"),
            MovimientoInventario.tipo,
            MovimientoInventario.cantidad,
            MovimientoInventario.referencia,
        )
        .select_from(MovimientoInventario)
        .join(Almacen, Almacen.id == MovimientoInventario.almacen_id)
        .join(Sku, Sku.id == MovimientoInventario.sku_id)
        .join(Articulo, Articulo.id == Sku.articulo_id)
        .where(
            MovimientoInventario.lote_id.is_(None),
            MovimientoInventario.cantidad < 0,
            Articulo.controla_lote.is_(True),
        )
        .order_by(MovimientoInventario.ts.desc())
        .limit(limite)
    )
    if empresa_id is not None:
        stmt = stmt.where(Almacen.empresa_id == empresa_id)
    if desde is not None:
        stmt = stmt.where(
            MovimientoInventario.ts >= fechas.inicio_dia_utc(desde)
        )
    if hasta is not None:
        stmt = stmt.where(MovimientoInventario.ts <= fechas.fin_dia_utc(hasta))

    return [
        {
            "fecha": fechas.a_fecha_local(fila.ts),
            "sku_id": fila.sku_id,
            "almacen": fila.almacen,
            "articulo": fila.articulo,
            "tipo": fila.tipo,
            "cantidad": -fila.cantidad,
            "referencia": fila.referencia,
        }
        for fila in session.execute(stmt)
    ]
