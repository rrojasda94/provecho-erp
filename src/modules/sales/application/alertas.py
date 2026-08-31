"""Alerta de pedido demorado: el pedido sigue en cocina pasado su umbral.

La revisión es **idempotente a propósito**. Hay dos caminos que la
disparan y pueden solaparse:

1. El listener de `sales.venta_confirmada` programa una revisión puntual
   para dentro de N minutos (llega justo a tiempo).
2. Un barrido periódico repasa todo lo que siga abierto (llega igual si el
   worker estuvo caído, si el broker perdió la tarea, o si la venta se
   creó mientras no había worker).

Se mantienen los dos porque para un sistema de alertas el modo de fallo que
importa es **no avisar**: la tarea puntual sola es silenciosamente frágil, y
el barrido solo llegaría hasta con un ciclo de retraso. Que ambos converjan
en la misma fila (con `UNIQUE (venta_id, minutos_umbral)` detrás) es lo que
hace seguro tenerlos juntos.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import AlertaPedido, Venta, VentaItem
from src.modules.users.infrastructure.models import Sucursal
from src.shared import parametros

# Umbral semilla. El valor real lo fija Gerencia por empresa
# (`parametro_empresa`, ADR-014) — acá vive el default del módulo.
CODIGO_UMBRAL = "minutos_alerta_pedido"
UMBRAL_DEFECTO_MINUTOS = 15

# Estados que significan "cocina todavía lo tiene".
EN_COCINA = ("pendiente", "en_preparacion")

# Una venta anulada no se demora: dejó de existir para la cocina. El resto sí,
# `orden` la primera: es el pedido enviado a cocina y todavía sin cobrar, o
# sea el caso normal de una mesa — decía `confirmada`, que no es ninguno de
# los cinco valores de `estado_venta`, y por eso la alerta nunca disparaba
# donde más falta hacía. `cerrada` es el consumo de personal, que también se
# prepara y también se demora.
ESTADOS_VIVOS = tuple(e for e in rules.ESTADOS_VENTA if e != "anulada")


def umbral_minutos(session: Session, empresa_id: uuid.UUID | None) -> int:
    """Minutos que puede tardar un pedido antes de alertar."""
    if empresa_id is None:
        return UMBRAL_DEFECTO_MINUTOS
    valor = parametros.valor_vigente(
        session, empresa_id, "sales", CODIGO_UMBRAL, default=None
    )
    if isinstance(valor, dict) and "minutos" in valor:
        return int(valor["minutos"])
    return UMBRAL_DEFECTO_MINUTOS


def _minutos_desde(momento: datetime, ahora: datetime) -> Decimal:
    if momento.tzinfo is None:
        # SQLite devuelve el timestamp sin zona; la base lo escribe en UTC.
        momento = momento.replace(tzinfo=ahora.tzinfo)
    return Decimal((ahora - momento).total_seconds()) / Decimal(60)


def revisar_pedido(
    session: Session, venta_id: uuid.UUID, *, ahora: datetime | None = None
) -> AlertaPedido | None:
    """Crea la alerta si el pedido sigue en cocina pasado el umbral.

    `None` = no había nada que alertar (pedido listo, entregado, anulado, o
    todavía dentro de tiempo) **o** la alerta ya existía. El llamador no
    distingue esos casos porque en ninguno tiene que hacer algo distinto.
    """
    ahora = ahora or datetime.now(tz=UTC)
    venta = session.get(Venta, venta_id)
    if venta is None or venta.estado not in ESTADOS_VIVOS:
        return None

    pendientes = list(
        session.scalars(
            select(VentaItem.estado_preparacion).where(
                VentaItem.venta_id == venta_id,
                VentaItem.estado_preparacion.in_(EN_COCINA),
            )
        )
    )
    if not pendientes:
        return None

    empresa_id = session.scalar(
        select(Sucursal.empresa_id).where(Sucursal.id == venta.sucursal_id)
    )
    umbral = umbral_minutos(session, empresa_id)
    transcurridos = _minutos_desde(venta.created_at, ahora)
    if transcurridos < umbral:
        return None

    # Camino normal de la idempotencia: se consulta antes de insertar. El
    # UNIQUE de abajo es para la carrera entre dos workers, no para el caso
    # habitual — provocar una excepción por cada barrido sería caro y
    # ensuciaría el log de la base.
    ya_existe = session.scalar(
        select(AlertaPedido.id).where(
            AlertaPedido.venta_id == venta.id,
            AlertaPedido.minutos_umbral == umbral,
        )
    )
    if ya_existe is not None:
        return None

    # `pendiente` pesa más que `en_preparacion`: significa que cocina ni lo
    # empezó. Se reporta el peor estado del pedido, no el primero que salga.
    estado = "pendiente" if "pendiente" in pendientes else "en_preparacion"

    alerta = AlertaPedido(
        venta_id=venta.id,
        sucursal_id=venta.sucursal_id,
        minutos_umbral=umbral,
        minutos_transcurridos=round(transcurridos, 2),
        estado_al_alertar=estado,
        items_pendientes=len(pendientes),
    )
    try:
        # SAVEPOINT: si otro worker se adelantó entre el SELECT de arriba y
        # este INSERT, se descarta **solo** esta alerta. Un `rollback()` de
        # la sesión entera se llevaría por delante las alertas que el mismo
        # barrido ya creó, y el trabajo del llamador.
        with session.begin_nested():
            session.add(alerta)
            session.flush()
    except IntegrityError:
        # Otro worker llegó primero. No es un error: es exactamente lo que
        # el UNIQUE está para evitar.
        return None

    event_bus.publish(
        "sales.pedido_demorado",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            "minutos_umbral": umbral,
            "minutos_transcurridos": str(alerta.minutos_transcurridos),
            "estado": estado,
            "items_pendientes": len(pendientes),
        },
        session=session,
    )
    return alerta


def barrer(session: Session, *, ahora: datetime | None = None) -> list[AlertaPedido]:
    """Revisa todo lo que siga en cocina. Es la red de seguridad de la
    revisión puntual: una tarea perdida deja de ser una alerta perdida.

    Solo mira ventas con ítems en cocina, no todo el historial.
    """
    ahora = ahora or datetime.now(tz=UTC)
    candidatas = list(
        session.scalars(
            select(Venta.id)
            .join(VentaItem, VentaItem.venta_id == Venta.id)
            .where(
                Venta.estado.in_(ESTADOS_VIVOS),
                VentaItem.estado_preparacion.in_(EN_COCINA),
            )
            .group_by(Venta.id)
        )
    )
    alertas = []
    for venta_id in candidatas:
        alerta = revisar_pedido(session, venta_id, ahora=ahora)
        if alerta is not None:
            alertas.append(alerta)
    return alertas


def atender(
    session: Session, alerta_id: uuid.UUID, usuario_id: uuid.UUID, nota: str | None
) -> AlertaPedido | None:
    """Cierra la alerta: alguien la vio y actuó. Reabrir no se contempla —
    si el pedido vuelve a demorarse es otra alerta, con otro umbral."""
    alerta = session.get(AlertaPedido, alerta_id)
    if alerta is None:
        return None
    if alerta.atendida_at is None:
        alerta.atendida_at = func.now()
        alerta.atendida_por = usuario_id
        alerta.nota = nota
    return alerta
