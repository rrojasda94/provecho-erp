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
    Receta,
    RecetaItem,
    Sku,
    SolicitudInsumos,
    SolicitudItem,
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
            total += recetas_uc.costo_linea(item, articulo)
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
    que nunca representaron una necesidad real.

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
        .where(SolicitudInsumos.estado != "cancelada")
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
