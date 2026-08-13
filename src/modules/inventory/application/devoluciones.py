"""Casos de uso de devolución (RN-INV-019/020).

Dos direcciones, y la dirección la decide **quién devuelve**:

- **A proveedor**: la mercadería sale. Se descuenta del almacén tomando el
  lote declarado —no el que FEFO elegiría, porque lo que se devuelve es
  justamente el lote malo— y se publica `inventory.devolucion_a_proveedor`
  para que `purchases` gestione el reclamo o la nota de crédito. Viaja por
  la vía pública, así que puede emitir su guía de remisión.
- **De cliente**: la mercadería entra, y `destino` decide qué pasa con ella
  (RN-INV-019). `reintegro` la suma a disponible; `desecho` y `auditoria`
  la ingresan y **acto seguido la apartan como merma**, porque físicamente
  está en el almacén pero no se puede vender.

La devolución **sucursal → central no pasa por acá**: es una transferencia
(ADR-020), que ya tiene despacho, tránsito y recepción con diferencias.
Duplicarla sería un segundo camino para el mismo movimiento.

`anular` existe porque una devolución mal registrada mueve stock real, y la
corrección tiene que ser un asiento contrario y no un `DELETE` que borra el
rastro de que alguien se equivocó.
"""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application import merma as merma_uc
from src.modules.inventory.application import reservas as reservas_uc
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import NoEncontrado, ReglaNegocio
from src.modules.inventory.infrastructure.models import Devolucion, DevolucionItem
from src.modules.inventory.infrastructure.repositories import DevolucionRepo
from src.shared import auditoria

ORIGENES = ("proveedor", "cliente")
MOTIVOS = (
    "vencido",
    "dañado",
    "incumplimiento_plazo",
    "no_requerido",
    "error_solicitud",
    "duplicidad",
)
DESTINOS = ("desecho", "auditoria", "reintegro")

# RN-INV-020: el reporte va a quien tiene que hacer algo con él. Si
# devolvemos al proveedor, es asunto de almacén; si devuelve un cliente, el
# problema es comercial.
REPORTE_POR_ORIGEN = {"proveedor": "almacen", "cliente": "comercial"}

# El destino de una devolución de cliente que no vuelve al estante se
# traduce al motivo con el que la merma queda apartada (RN-INV-012).
MOTIVO_MERMA = {"desecho": "devolucion", "auditoria": "auditoria"}


def registrar_devolucion(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    origen: str,
    motivo: str,
    registrado_por: uuid.UUID,
    items: list[dict],
    referencia_id: uuid.UUID | None = None,
    destino: str | None = None,
    observacion: str | None = None,
) -> Devolucion:
    if origen not in ORIGENES:
        raise ReglaNegocio(f"origen de devolución inválido: {origen}")
    if motivo not in MOTIVOS:
        raise ReglaNegocio(f"motivo de devolución inválido: {motivo}")
    if not items:
        raise ReglaNegocio("una devolución sin ítems no devuelve nada")
    if origen == "cliente":
        if destino not in DESTINOS:
            raise ReglaNegocio(
                "una devolución de cliente exige destino: qué se hace con lo "
                "que volvió (RN-INV-019)"
            )
    elif destino is not None:
        raise ReglaNegocio(
            "una devolución a proveedor no lleva destino: la mercadería se va"
        )

    devolucion = DevolucionRepo(session).add(
        Devolucion(
            almacen_id=almacen_id,
            origen=origen,
            referencia_id=referencia_id,
            motivo=motivo,
            destino=destino,
            estado="registrada",
            reporte_dirigido_a=REPORTE_POR_ORIGEN[origen],
            observacion=observacion,
            registrado_por=registrado_por,
        )
    )

    for linea in items:
        item = _agregar_item(session, devolucion, linea)
        _mover_stock(session, devolucion, item, registrado_por, signo=1)

    lineas = DevolucionRepo(session).items(devolucion.id)
    # Mueve stock real, así que deja rastro como el ajuste (RN-AUD-001). El
    # evento le avisa a purchases o a comercial; el `audit_log` responde
    # "quién sacó esto del almacén y cuándo", que es otra pregunta.
    auditoria.registrar(
        session,
        usuario_id=registrado_por,
        entidad="devolucion",
        entidad_id=devolucion.id,
        accion="registrar",
        datos_despues={
            "origen": origen,
            "motivo": motivo,
            "destino": destino,
            "almacen_id": str(almacen_id),
            "items": [
                {"sku_id": str(i.sku_id), "cantidad": str(i.cantidad)} for i in lineas
            ],
        },
    )

    event_bus.publish(
        _EVENTO[origen],
        {
            "devolucion_id": str(devolucion.id),
            "almacen_id": str(almacen_id),
            "referencia_id": str(referencia_id) if referencia_id else None,
            "motivo": motivo,
            "destino": destino,
            "reporte_dirigido_a": devolucion.reporte_dirigido_a,
            "registrado_por": str(registrado_por) if registrado_por else None,
            "items": [
                {
                    "sku_id": str(i.sku_id),
                    "lote_id": str(i.lote_id) if i.lote_id else None,
                    "cantidad": str(i.cantidad),
                }
                for i in DevolucionRepo(session).items(devolucion.id)
            ],
        },
        session=session,
    )
    return devolucion


_EVENTO = {
    "proveedor": "inventory.devolucion_a_proveedor",
    "cliente": "inventory.devolucion_de_cliente",
}


def _agregar_item(
    session: Session, devolucion: Devolucion, linea: dict
) -> DevolucionItem:
    cantidad = Decimal(str(linea["cantidad"]))
    if cantidad <= 0:
        raise ReglaNegocio("la cantidad devuelta debe ser > 0")
    sku_id = linea["sku_id"]
    lote_id = linea.get("lote_id")
    articulo = lotes_uc.articulo_de_sku(session, sku_id)
    if lote_id is None and articulo.controla_lote and devolucion.origen == "proveedor":
        # Al proveedor se le devuelve un lote concreto: es la única forma de
        # que el reclamo diga qué mercadería se rechaza.
        raise ReglaNegocio(
            f"'{articulo.nombre}' controla lote: la devolución debe indicar cuál"
        )
    return DevolucionRepo(session).add_item(
        DevolucionItem(
            devolucion_id=devolucion.id,
            sku_id=sku_id,
            cantidad=cantidad,
            lote_id=lote_id,
        )
    )


def _mover_stock(
    session: Session,
    devolucion: Devolucion,
    item: DevolucionItem,
    usuario_id: uuid.UUID,
    *,
    signo: int,
) -> None:
    """Un movimiento tipo `devolucion` por línea, con el lote declarado."""
    sale = (devolucion.origen == "proveedor") == (signo > 0)
    if sale:
        stock_uc.registrar_salida(
            session,
            almacen_id=devolucion.almacen_id,
            sku_id=item.sku_id,
            cantidad=item.cantidad,
            tipo="devolucion",
            usuario_id=usuario_id,
            referencia=str(devolucion.id),
            lote_id=item.lote_id,
            motivo_lote=f"devolución por {devolucion.motivo}",
        )
        return

    stock_uc.registrar_movimiento(
        session,
        almacen_id=devolucion.almacen_id,
        sku_id=item.sku_id,
        cantidad=item.cantidad,
        tipo="devolucion",
        usuario_id=usuario_id,
        referencia=str(devolucion.id),
        lote_id=item.lote_id,
    )
    if signo > 0 and devolucion.destino in MOTIVO_MERMA:
        # Entró al almacén pero no al estante: se aparta en el mismo acto
        # para que ninguna venta la tome mientras espera auditoría. Cuelga de
        # la devolución (`referencia_id`) para poder soltarla si se anula.
        merma_uc.registrar_merma(
            session,
            almacen_id=devolucion.almacen_id,
            sku_id=item.sku_id,
            cantidad=item.cantidad,
            motivo=MOTIVO_MERMA[devolucion.destino],
            creado_por=usuario_id,
            lote_id=item.lote_id,
            referencia_id=devolucion.id,
        )


def anular_devolucion(
    session: Session, devolucion_id: uuid.UUID, anulado_por: uuid.UUID
) -> Devolucion:
    """Repone lo que la devolución movió, con movimientos contrarios."""
    repo = DevolucionRepo(session)
    devolucion = repo.get(devolucion_id)
    if devolucion is None:
        raise NoEncontrado("devolución no encontrada")
    if devolucion.estado != "registrada":
        raise ReglaNegocio(f"la devolución ya está {devolucion.estado}")
    if repo.guia(devolucion_id) is not None:
        raise ReglaNegocio(
            "la devolución ya tiene guía de remisión emitida: anularla exige "
            "primero la comunicación de baja ante SUNAT"
        )

    # Primero se sueltan las mermas que la devolución apartó: si no, el
    # movimiento contrario sacaría stock que una reserva viva sigue
    # descontando del disponible, y el número quedaría negativo por nada.
    reservas_uc.liberar_por_referencia(session, devolucion_id, anulado_por)
    for item in repo.items(devolucion_id):
        _mover_stock(session, devolucion, item, anulado_por, signo=-1)
    devolucion.estado = "anulada"
    devolucion.anulado_por = anulado_por
    devolucion.anulada_at = datetime.datetime.now(datetime.UTC)
    # Anular devuelve stock al almacén: es exactamente el movimiento que
    # alguien podría usar para tapar un faltante, así que tiene que decir
    # quién lo hizo (RN-AUD-001).
    auditoria.registrar(
        session,
        usuario_id=anulado_por,
        entidad="devolucion",
        entidad_id=devolucion.id,
        accion="anular",
        datos_antes={"estado": "registrada"},
        datos_despues={"estado": "anulada", "motivo": devolucion.motivo},
    )
    return devolucion


def detalle(
    session: Session, devolucion_id: uuid.UUID
) -> tuple[Devolucion, list[DevolucionItem]]:
    repo = DevolucionRepo(session)
    devolucion = repo.get(devolucion_id)
    if devolucion is None:
        raise NoEncontrado("devolución no encontrada")
    return devolucion, repo.items(devolucion_id)


def listar(
    session: Session,
    *,
    almacen_id: uuid.UUID | None = None,
    origen: str | None = None,
    empresa_id: uuid.UUID | None = None,
) -> list[Devolucion]:
    return DevolucionRepo(session).listar(
        almacen_id=almacen_id, origen=origen, empresa_id=empresa_id
    )
