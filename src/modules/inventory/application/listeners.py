"""Listeners de eventos de otros módulos → movimientos de inventario.

`sales.venta_confirmada` descuenta insumos según receta (+ merma % +
empaque por modalidad); `sales.venta_anulada` repone.
`sales.consumo_personal_registrado` descuenta igual pero con tipo
`consumo_interno` y valoriza lo consumido, para que contabilidad lo lleve a
gasto de alimentación de personal (RN-COM-025). La comunicación es solo vía
event bus — nunca imports del dominio de sales.

Un fallo de inventario NUNCA rompe la venta: el handler atrapa y loguea.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import StockInsuficiente
from src.modules.inventory.infrastructure.models import (
    Articulo,
    IncidenciaInventario,
    RecetaItem,
    Sku,
)
from src.modules.inventory.infrastructure.repositories import StockRepo

# Almacén/Sucursal son organización transversal (data-model §1); viven en
# users/infrastructure por historia. Import de modelo (no dominio) permitido.
from src.modules.users.infrastructure.models import Almacen, Sucursal

log = logging.getLogger(__name__)

# Inyectable (tests la reemplazan). El listener commitea su propia sesión;
# el bus solo lo despierta después de que la venta commiteó (`core/events`),
# así que lo que mueve acá corresponde a una venta que ya existe. Sigue sin
# ser atómico con ella: si este commit falla, la venta queda igual y la
# discrepancia la detecta el conteo — outbox real cuando llegue Celery.
session_factory = SessionLocal


def _almacen_de_sucursal(session: Session, sucursal_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        select(Almacen.id).where(
            Almacen.sucursal_id == sucursal_id, Almacen.deleted_at.is_(None)
        )
    )


def _omitir(
    session: Session,
    *,
    empresa_id: uuid.UUID | None,
    origen: str,
    referencia: str,
    tipo: str,
    detalle: str,
    almacen_id: uuid.UUID | None = None,
    articulo_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    cantidad: Decimal | None = None,
) -> None:
    """Deja constancia consultable de un movimiento que no se hizo.

    Sigue logueando: el log sirve para depurar en el momento, la fila sirve
    para que alguien lo vea la semana que viene. Sin `empresa_id` no se
    puede guardar sin romper el filtro de tenant, así que en ese caso —que
    solo pasa con datos de organización incoherentes— queda el log solo.
    """
    log.warning("%s %s: %s", origen, referencia, detalle)
    if empresa_id is None:
        return
    session.add(
        IncidenciaInventario(
            empresa_id=empresa_id,
            origen=origen,
            referencia=referencia,
            tipo=tipo,
            almacen_id=almacen_id,
            articulo_id=articulo_id,
            sku_id=sku_id,
            cantidad=cantidad,
            detalle=detalle,
        )
    )


def _empresa_de_almacen(session: Session, almacen_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(select(Almacen.empresa_id).where(Almacen.id == almacen_id))


def _sku_de_articulo(session: Session, articulo_id: uuid.UUID) -> uuid.UUID | None:
    # ponytail: SKU activo de mayor prioridad; elección por lote llega con FEFO.
    return session.scalar(
        select(Sku.id)
        .where(Sku.articulo_id == articulo_id, Sku.activo.is_(True))
        .order_by(Sku.prioridad)
    )


def _consumos_de_items(session: Session, items: list[dict]) -> list[tuple[uuid.UUID, Decimal]]:
    """Expande items de venta → [(articulo_id, cantidad_a_consumir)]."""
    consumos: list[tuple[uuid.UUID, Decimal]] = []
    for it in items:
        cantidad_vendida = Decimal(it["cantidad"])
        # Restas de la línea ("sin cebolla", RN-PRD-004): el insumo quitado
        # no se descuenta. La resta actúa acá y no en el precio a propósito
        # —quitar cebolla no abarata la pizza—, pero sí tiene que mover el
        # inventario: si no, la cebolla que quedó en la cámara aparece como
        # faltante en el conteo del mes.
        sin = {str(a) for a in (it.get("sin_articulo_ids") or [])}
        for ri in session.scalars(
            select(RecetaItem).where(RecetaItem.receta_id == uuid.UUID(it["receta_id"]))
        ):
            if str(ri.articulo_id) in sin:
                continue
            # Consumo = cantidad de receta × vendido × (1 + merma%).
            consumo = (
                ri.cantidad * cantidad_vendida * (1 + ri.merma_pct / 100)
            )
            consumos.append((ri.articulo_id, consumo))
        if it.get("empaque_articulo_id"):
            consumos.append(
                (uuid.UUID(it["empaque_articulo_id"]), cantidad_vendida)
            )
    return consumos


def _mover(payload: dict, tipo: str, signo: int, valorizar: bool = False) -> None:
    """Descuenta (o repone) el insumo de una venta.

    `valorizar=True` suma además cuánto costó lo que salió, a costo promedio
    del artículo, y lo publica: es el único punto del ERP que conoce las
    líneas de consumo reales, así que valorizar en otro lado daría un número
    distinto al que movió el stock (mismo criterio que `merma`).
    """
    # Un solo exit con commit SIEMPRE: un return temprano cerraría la sesión
    # con rollback, y con conexión compartida (SQLite en tests) ese rollback
    # se llevaría también lo ya movido en esta misma sesión.
    movio = False
    monto = Decimal(0)
    with session_factory() as session:
        sucursal_id = uuid.UUID(payload["sucursal_id"])
        almacen_id = _almacen_de_sucursal(session, sucursal_id)
        empresa_id = session.scalar(
            select(Sucursal.empresa_id).where(Sucursal.id == sucursal_id)
        )
        if almacen_id is None:
            _omitir(
                session,
                empresa_id=empresa_id,
                origen="venta",
                referencia=payload["venta_id"],
                tipo="sin_almacen",
                detalle="la sucursal no tiene almacén: no se descontó nada",
            )
        else:
            for articulo_id, cantidad in _consumos_de_items(session, payload["items"]):
                sku_id = _sku_de_articulo(session, articulo_id)
                if sku_id is None:
                    _omitir(
                        session,
                        empresa_id=empresa_id,
                        origen="venta",
                        referencia=payload["venta_id"],
                        tipo="sin_sku",
                        detalle="el artículo no tiene SKU activo",
                        almacen_id=almacen_id,
                        articulo_id=articulo_id,
                        cantidad=cantidad,
                    )
                    continue
                try:
                    if signo < 0:
                        # FEFO: la venta se lleva primero lo que vence antes.
                        stock_uc.registrar_salida(
                            session,
                            almacen_id=almacen_id,
                            sku_id=sku_id,
                            cantidad=cantidad,
                            tipo=tipo,
                            referencia=payload["venta_id"],
                        )
                    else:
                        # ponytail: la reposición por anulación entra al lote
                        # del día, no al lote del que salió — el movimiento
                        # original no viaja en el evento. Ver deuda del módulo.
                        stock_uc.registrar_movimiento(
                            session,
                            almacen_id=almacen_id,
                            sku_id=sku_id,
                            cantidad=cantidad,
                            tipo=tipo,
                            referencia=payload["venta_id"],
                        )
                    movio = True
                    if valorizar:
                        articulo = session.get(Articulo, articulo_id)
                        if articulo is not None:
                            monto += cantidad * articulo.costo_promedio
                except StockInsuficiente:
                    # ponytail: la venta ya ocurrió — el stock teórico no la
                    # bloquea; queda la discrepancia para conteo/ajuste.
                    _omitir(
                        session,
                        empresa_id=empresa_id,
                        origen="venta",
                        referencia=payload["venta_id"],
                        tipo="stock_insuficiente",
                        detalle="el stock teórico no alcanzaba para el consumo",
                        almacen_id=almacen_id,
                        articulo_id=articulo_id,
                        sku_id=sku_id,
                        cantidad=cantidad,
                    )
        if movio:
            event_bus.publish(
                "inventory.stock_consumido"
                if signo < 0
                else "inventory.stock_repuesto",
                {"venta_id": payload["venta_id"]},
                session=session,
            )
        if valorizar and monto > 0:
            event_bus.publish(
                "inventory.consumo_personal_valorizado",
                {
                    "venta_id": payload["venta_id"],
                    "sucursal_id": payload["sucursal_id"],
                    "empresa_id": str(empresa_id) if empresa_id else None,
                    "motivo": payload.get("consumo_motivo"),
                    "monto": str(monto),
                },
                session=session,
            )
        session.commit()


def on_venta_confirmada(payload: dict) -> None:
    try:
        _mover(payload, tipo="consumo_venta", signo=-1)
    except Exception:
        log.exception("fallo consumiendo stock de venta %s", payload.get("venta_id"))


def on_consumo_personal(payload: dict) -> None:
    """La comida del personal sale del almacén como cualquier pedido, pero
    con su propio tipo de movimiento y valorizada: su costo es gasto de
    alimentación de personal, no costo de ventas (RN-COM-025)."""
    try:
        _mover(payload, tipo="consumo_interno", signo=-1, valorizar=True)
    except Exception:
        log.exception(
            "fallo consumiendo stock de consumo de personal %s",
            payload.get("venta_id"),
        )


def on_venta_anulada(payload: dict) -> None:
    try:
        _mover(payload, tipo="devolucion", signo=+1)
        # Solo la anulación completa reversa el gasto: quitar una línea de un
        # consumo de personal devuelve su insumo, pero el asiento cubre la
        # orden entera y reversarlo dejaría sin gasto a las líneas que sí se
        # comieron (RN-COM-027).
        if payload.get("tipo") == "consumo_personal" and payload.get("venta_anulada"):
            _reversar_consumo_personal(payload)
    except Exception:
        log.exception("fallo reponiendo stock de venta %s", payload.get("venta_id"))


def _reversar_consumo_personal(payload: dict) -> None:
    """Avisa que el gasto de ese consumo ya no existe. Sin esto la reposición
    del insumo dejaría el gasto de alimentación de personal inflado por algo
    que nadie comió."""
    with session_factory() as session:
        empresa_id = session.scalar(
            select(Sucursal.empresa_id).where(
                Sucursal.id == uuid.UUID(payload["sucursal_id"])
            )
        )
        event_bus.publish(
            "inventory.consumo_personal_reversado",
            {
                "venta_id": payload["venta_id"],
                "empresa_id": str(empresa_id) if empresa_id else None,
            },
            session=session,
        )
        session.commit()


def _actualizar_costo_promedio(
    session: Session,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    costo_unitario: Decimal,
) -> None:
    # ponytail: promedio ponderado solo contra el stock del SKU en el
    # almacén que recibe (no consolida todos los almacenes del artículo) —
    # razonable mientras casi toda compra entra por almacén central;
    # revisar si compra_directa multi-almacén se vuelve frecuente.
    sku = session.get(Sku, sku_id)
    articulo = session.get(Articulo, sku.articulo_id)
    stock_previo = StockRepo(session).get(almacen_id, sku_id)
    cantidad_previa = stock_previo.cantidad if stock_previo else Decimal(0)
    total_nuevo = cantidad_previa + cantidad
    if total_nuevo > 0:
        articulo.costo_promedio = (
            (cantidad_previa * articulo.costo_promedio) + (cantidad * costo_unitario)
        ) / total_nuevo


def _lote_del_ingreso(
    session: Session,
    articulo_id: uuid.UUID,
    origen: str,
    referencia: str,
    datos: dict,
) -> uuid.UUID | None:
    """Crea (o reusa) el lote del ingreso si el artículo lo controla.

    La fecha de vencimiento la declara el proveedor en la recepción
    (RN-VNC-002) o la normativa/laboratorio en producción (RN-VNC-001);
    si el evento no la trae, el lote nace sin vencimiento y FEFO lo trata
    como FIFO.
    """
    articulo = session.get(Articulo, articulo_id)
    if articulo is None or not articulo.controla_lote:
        return None
    vence = datos.get("fecha_vencimiento")
    return lotes_uc.crear_lote(
        session,
        articulo_id=articulo_id,
        codigo=datos.get("lote_codigo"),
        fecha_vencimiento=date.fromisoformat(vence) if vence else None,
        origen=origen,
        referencia=referencia,
    ).id


def on_compra_recibida(payload: dict) -> None:
    try:
        with session_factory() as session:
            almacen_id = uuid.UUID(payload["almacen_destino_id"])
            empresa_id = _empresa_de_almacen(session, almacen_id)
            for it in payload["items"]:
                articulo_id = uuid.UUID(it["articulo_id"])
                sku_id = _sku_de_articulo(session, articulo_id)
                if sku_id is None:
                    _omitir(
                        session,
                        empresa_id=empresa_id,
                        origen="orden_compra",
                        referencia=payload["orden_compra_id"],
                        tipo="sin_sku",
                        detalle="el artículo recibido no tiene SKU activo",
                        almacen_id=almacen_id,
                        articulo_id=articulo_id,
                        cantidad=Decimal(it["cantidad"]),
                    )
                    continue
                cantidad = Decimal(it["cantidad"])
                costo_unitario = Decimal(it["costo_unitario"])
                _actualizar_costo_promedio(
                    session, almacen_id, sku_id, cantidad, costo_unitario
                )
                stock_uc.registrar_movimiento(
                    session,
                    almacen_id=almacen_id,
                    sku_id=sku_id,
                    cantidad=cantidad,
                    tipo="recepcion_compra",
                    referencia=payload["orden_compra_id"],
                    lote_id=_lote_del_ingreso(
                        session, articulo_id, "compra",
                        payload["orden_compra_id"], it,
                    ),
                )
            session.commit()
    except Exception:
        log.exception(
            "fallo ingresando stock de la OC %s", payload.get("orden_compra_id")
        )


def on_consumo_registrado(payload: dict) -> None:
    try:
        with session_factory() as session:
            almacen_id = uuid.UUID(payload["almacen_id"])
            empresa_id = _empresa_de_almacen(session, almacen_id)
            for it in payload["items"]:
                articulo_id = uuid.UUID(it["articulo_id"])
                cantidad = Decimal(it["cantidad"])
                sku_id = _sku_de_articulo(session, articulo_id)
                if sku_id is None:
                    _omitir(
                        session,
                        empresa_id=empresa_id,
                        origen="orden_produccion",
                        referencia=payload["orden_produccion_id"],
                        tipo="sin_sku",
                        detalle="el insumo no tiene SKU activo",
                        almacen_id=almacen_id,
                        articulo_id=articulo_id,
                        cantidad=cantidad,
                    )
                    continue
                try:
                    stock_uc.registrar_salida(
                        session,
                        almacen_id=almacen_id,
                        sku_id=sku_id,
                        cantidad=cantidad,
                        tipo="consumo_produccion",
                        referencia=payload["orden_produccion_id"],
                    )
                except StockInsuficiente:
                    # ponytail: mismo criterio que venta — el consumo real ya
                    # ocurrió en cocina, el stock teórico no lo bloquea.
                    _omitir(
                        session,
                        empresa_id=empresa_id,
                        origen="orden_produccion",
                        referencia=payload["orden_produccion_id"],
                        tipo="stock_insuficiente",
                        detalle="el stock teórico no alcanzaba para el consumo",
                        almacen_id=almacen_id,
                        articulo_id=articulo_id,
                        sku_id=sku_id,
                        cantidad=cantidad,
                    )
            session.commit()
    except Exception:
        log.exception(
            "fallo consumiendo stock de la orden %s", payload.get("orden_produccion_id")
        )


def on_orden_completada(payload: dict) -> None:
    try:
        with session_factory() as session:
            almacen_id = uuid.UUID(payload["almacen_id"])
            sku_id = _sku_de_articulo(session, uuid.UUID(payload["articulo_id"]))
            if sku_id is None:
                _omitir(
                    session,
                    empresa_id=_empresa_de_almacen(session, almacen_id),
                    origen="orden_produccion",
                    referencia=payload["orden_produccion_id"],
                    tipo="sin_sku",
                    detalle="el producto terminado no tiene SKU activo: no ingresó",
                    almacen_id=almacen_id,
                    articulo_id=uuid.UUID(payload["articulo_id"]),
                    cantidad=Decimal(payload["cantidad_producida"]),
                )
                session.commit()
                return
            cantidad = Decimal(payload["cantidad_producida"])
            costo_unitario = Decimal(payload["costo_unitario"])
            _actualizar_costo_promedio(session, almacen_id, sku_id, cantidad, costo_unitario)
            stock_uc.registrar_movimiento(
                session,
                almacen_id=almacen_id,
                sku_id=sku_id,
                cantidad=cantidad,
                tipo="produccion_entrada",
                referencia=payload["orden_produccion_id"],
                lote_id=_lote_del_ingreso(
                    session,
                    uuid.UUID(payload["articulo_id"]),
                    "produccion",
                    payload["orden_produccion_id"],
                    payload,
                ),
            )
            session.commit()
    except Exception:
        log.exception(
            "fallo ingresando stock de la orden %s", payload.get("orden_produccion_id")
        )


_registrado = False


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_confirmada", on_venta_confirmada)
    event_bus.subscribe("sales.consumo_personal_registrado", on_consumo_personal)
    event_bus.subscribe("sales.venta_anulada", on_venta_anulada)
    # Anular líneas sueltas repone igual que anular la venta entera: el
    # payload trae solo las líneas quitadas.
    event_bus.subscribe("sales.lineas_anuladas", on_venta_anulada)
    # La nota de crédito repone igual, cuando quien la emite lo pidió: si no,
    # el evento viaja con `items` vacío y esto no mueve nada (RN-CPP-009).
    event_bus.subscribe("sales.nota_credito_emitida", on_venta_anulada)
    event_bus.subscribe("purchases.compra_recibida", on_compra_recibida)
    event_bus.subscribe("production.consumo_registrado", on_consumo_registrado)
    event_bus.subscribe("production.orden_completada", on_orden_completada)
