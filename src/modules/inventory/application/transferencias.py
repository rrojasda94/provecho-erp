"""Casos de uso de transferencia entre almacenes (RN-INV-001..003).

Despachar descuenta el origen; recibir suma el destino. Entre ambos
momentos el stock está `en_transito` — descontado de un lado y todavía no
ingresado del otro, que es exactamente lo que pasa en la carretera.

Dos entradas al mismo flujo:
- **Surtiendo una solicitud aprobada**: toma las cantidades aprobadas y
  consume las reservas que la aprobación dejó.
- **Transferencia lateral** sucursal↔sucursal, sin solicitud: los ítems
  vienen en el request. Misma entidad, `solicitud_id` en NULL.

El despacho reparte por FEFO, así que una línea de 10 kg puede salir de
tres lotes y genera tres `transferencia_item`: el destino recibe los
mismos lotes que salieron (ADR-015).
"""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import reservas as reservas_uc
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import (
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import (
    Transferencia,
    TransferenciaItem,
)
from src.modules.inventory.infrastructure.repositories import (
    SolicitudRepo,
    TransferenciaRepo,
)
from src.modules.users.infrastructure.models import Almacen


def _exigir_almacen(session: Session, almacen_id: uuid.UUID, rol: str) -> Almacen:
    almacen = session.get(Almacen, almacen_id)
    if almacen is None or almacen.deleted_at is not None:
        raise NoEncontrado(f"almacén {rol} no encontrado")
    return almacen


def despachar(
    session: Session,
    *,
    origen_almacen_id: uuid.UUID,
    destino_almacen_id: uuid.UUID,
    despachado_por: uuid.UUID,
    solicitud_id: uuid.UUID | None = None,
    items: list[tuple[uuid.UUID, Decimal]] | None = None,
    transportista_id: uuid.UUID | None = None,
    observacion: str | None = None,
) -> Transferencia:
    """Saca el stock del origen y lo deja en tránsito.

    Con `solicitud_id`, `items` recorta lo despachado por SKU; sin él se
    despacha lo aprobado. Nunca más de lo aprobado (RN-INV-001) — menos
    sí: si el central no tiene todo, sale lo que hay y la diferencia queda
    a la vista en la solicitud.
    """
    _validar_almacenes(session, origen_almacen_id, destino_almacen_id)
    solicitud = _solicitud_despachable(
        session, solicitud_id, origen_almacen_id, destino_almacen_id
    )
    a_despachar = _resolver_lineas(session, solicitud_id, items)
    if not a_despachar:
        raise ReglaNegocio("no hay nada que despachar")

    repo = TransferenciaRepo(session)
    transferencia = repo.add(
        Transferencia(
            origen_almacen_id=origen_almacen_id,
            destino_almacen_id=destino_almacen_id,
            solicitud_id=solicitud_id,
            estado="en_transito",
            despachado_por=despachado_por,
            transportista_id=transportista_id,
            observacion=observacion,
        )
    )
    for sku_id, cantidad in a_despachar:
        # La reserva se cierra ANTES de mover el stock: si no, el físico
        # baja y la reserva sigue viva, y el disponible quedaría
        # descontado dos veces por la misma promesa.
        if solicitud_id is not None:
            reservas_uc.consumir_por_referencia(session, solicitud_id, sku_id)
        movimientos = stock_uc.registrar_salida(
            session,
            almacen_id=origen_almacen_id,
            sku_id=sku_id,
            cantidad=cantidad,
            tipo="transferencia_salida",
            usuario_id=despachado_por,
            referencia=str(transferencia.id),
        )
        for mov in movimientos:
            repo.add_item(
                TransferenciaItem(
                    transferencia_id=transferencia.id,
                    sku_id=sku_id,
                    lote_id=mov.lote_id,
                    cantidad_enviada=-mov.cantidad,
                )
            )

    if solicitud is not None:
        despachadas = dict(a_despachar)
        for item in SolicitudRepo(session).items(solicitud.id):
            item.cantidad_despachada = despachadas.get(item.sku_id, Decimal(0))
        solicitud.estado = "despachada"
    return transferencia


def _validar_almacenes(
    session: Session, origen_almacen_id: uuid.UUID, destino_almacen_id: uuid.UUID
) -> None:
    if origen_almacen_id == destino_almacen_id:
        raise ReglaNegocio("origen y destino no pueden ser el mismo almacén")
    origen = _exigir_almacen(session, origen_almacen_id, "origen")
    destino = _exigir_almacen(session, destino_almacen_id, "destino")
    if origen.empresa_id != destino.empresa_id:
        raise ReglaNegocio("los dos almacenes deben ser de la misma empresa")


def _solicitud_despachable(
    session: Session,
    solicitud_id: uuid.UUID | None,
    origen_almacen_id: uuid.UUID,
    destino_almacen_id: uuid.UUID,
):
    """La transferencia que surte una solicitud tiene que ir justo entre
    los dos almacenes que esa solicitud nombró — si no, el stock viaja a
    otro lado y la solicitud queda marcada como atendida igual."""
    if solicitud_id is None:
        return None
    solicitud = SolicitudRepo(session).get(solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    if solicitud.estado != "aprobada":
        raise ReglaNegocio(
            f"solo se despacha una solicitud aprobada, está {solicitud.estado}"
        )
    if solicitud.almacen_abastecedor_id != origen_almacen_id:
        raise ReglaNegocio("el origen no es el abastecedor de esa solicitud")
    if solicitud.almacen_solicitante_id != destino_almacen_id:
        raise ReglaNegocio("el destino no es quien hizo esa solicitud")
    return solicitud


def _resolver_lineas(
    session: Session,
    solicitud_id: uuid.UUID | None,
    items: list[tuple[uuid.UUID, Decimal]] | None,
) -> list[tuple[uuid.UUID, Decimal]]:
    if solicitud_id is None:
        if not items:
            raise ReglaNegocio(
                "una transferencia sin solicitud necesita ítems explícitos"
            )
        for _, cantidad in items:
            if cantidad <= 0:
                raise ReglaNegocio("la cantidad a despachar debe ser positiva")
        return items

    aprobadas = {
        item.sku_id: item.cantidad_aprobada
        for item in SolicitudRepo(session).items(solicitud_id)
    }
    pedidos = items if items is not None else [
        (sku_id, cantidad) for sku_id, cantidad in aprobadas.items() if cantidad
    ]
    lineas = []
    for sku_id, cantidad in pedidos:
        if sku_id not in aprobadas:
            raise ReglaNegocio("el SKU no está en la solicitud")
        if not rules.puede_despachar(aprobadas[sku_id], cantidad):
            raise ReglaNegocio(
                f"no se despacha más de lo aprobado: aprobado "
                f"{aprobadas[sku_id]}, se intenta despachar {cantidad}"
            )
        lineas.append((sku_id, cantidad))
    return lineas


def recibir(
    session: Session,
    transferencia_id: uuid.UUID,
    recibido_por: uuid.UUID,
    recibidas: dict[uuid.UUID, Decimal] | None = None,
) -> Transferencia:
    """Ingresa al destino lo que llegó, lote por lote.

    `recibidas` mapea `transferencia_item.id` → cantidad; lo que no se
    menciona se recibe completo. Una diferencia contra lo enviado no se
    corrige sola: entra al stock lo que de verdad llegó y la diferencia
    queda registrada para auditarse (RN-INV-002).
    """
    repo = TransferenciaRepo(session)
    transferencia = repo.get(transferencia_id)
    if transferencia is None:
        raise NoEncontrado("transferencia no encontrada")
    if transferencia.estado != "en_transito":
        raise ReglaNegocio(f"la transferencia ya está {transferencia.estado}")

    recibidas = recibidas or {}
    diferencias = []
    for item in repo.items(transferencia_id):
        cantidad = recibidas.get(item.id, item.cantidad_enviada)
        if cantidad < 0:
            raise ReglaNegocio("la cantidad recibida no puede ser negativa")
        if cantidad > item.cantidad_enviada:
            raise ReglaNegocio(
                "no se recibe más de lo enviado: enviado "
                f"{item.cantidad_enviada}, se declara recibido {cantidad}"
            )
        item.cantidad_recibida = cantidad
        if cantidad > 0:
            stock_uc.registrar_movimiento(
                session,
                almacen_id=transferencia.destino_almacen_id,
                sku_id=item.sku_id,
                cantidad=cantidad,
                tipo="transferencia_entrada",
                usuario_id=recibido_por,
                referencia=str(transferencia.id),
                lote_id=item.lote_id,
            )
        if item.diferencia:
            diferencias.append(
                {
                    "sku_id": str(item.sku_id),
                    "lote_id": str(item.lote_id) if item.lote_id else None,
                    "enviada": str(item.cantidad_enviada),
                    "recibida": str(cantidad),
                }
            )

    transferencia.estado = "recibida"
    transferencia.recibido_por = recibido_por
    transferencia.recibida_at = datetime.datetime.now(datetime.UTC)
    if transferencia.solicitud_id is not None:
        solicitud = SolicitudRepo(session).get(transferencia.solicitud_id)
        if solicitud is not None:
            solicitud.estado = "recibida"

    event_bus.publish(
        "inventory.transferencia_recibida",
        {
            "transferencia_id": str(transferencia.id),
            "origen_almacen_id": str(transferencia.origen_almacen_id),
            "destino_almacen_id": str(transferencia.destino_almacen_id),
            "solicitud_id": (
                str(transferencia.solicitud_id)
                if transferencia.solicitud_id
                else None
            ),
            "diferencias": diferencias,
        },
    )
    return transferencia


def detalle(
    session: Session, transferencia_id: uuid.UUID
) -> tuple[Transferencia, list[TransferenciaItem]]:
    repo = TransferenciaRepo(session)
    transferencia = repo.get(transferencia_id)
    if transferencia is None:
        raise NoEncontrado("transferencia no encontrada")
    return transferencia, repo.items(transferencia_id)


def listar(
    session: Session,
    *,
    almacen_id: uuid.UUID | None = None,
    estado: str | None = None,
    empresa_id: uuid.UUID | None = None,
) -> list[Transferencia]:
    return TransferenciaRepo(session).list(almacen_id, estado, empresa_id)
