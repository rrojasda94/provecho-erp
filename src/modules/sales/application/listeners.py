"""Listeners de `sales`.

Al confirmarse una venta se programa la revisión de demora para dentro del
umbral — ese handler **no revisa nada**, encola y vuelve, porque el bus es
síncrono y en proceso (`core/events.py`) y bloquear acá esperando 15
minutos congelaría la caja que confirmó la venta.

El segundo handler (`delivery.entrega_registrada`) sí abre su propia
sesión: es la mitad `sales` del cierre de la rama delivery de
`PROC-OPE-002` (ADR-098) — `delivery` nunca importa `cumplimiento`
directamente, publica el evento y este handler hace la llamada real.
"""

import logging
import uuid
from datetime import date

from src.core.database import SessionLocal
from src.core.events import event_bus

log = logging.getLogger(__name__)

# Inyectable (los tests la reemplazan, ver `MODULOS_CON_SESSION_FACTORY` en
# `tests/conftest.py`). Solo lo usa `on_entrega_registrada`: el handler de
# `venta_confirmada` no toca la base, así que sembrarlo acá no le costaba
# nada a los tests hasta que este segundo handler lo hizo necesario.
session_factory = SessionLocal

_registrado = False


def on_venta_confirmada(payload: dict) -> None:
    """Programa la revisión de demora del pedido recién enviado a cocina.

    La importación va adentro para no arrastrar Celery (ni su broker) al
    importar este módulo: los tests del dominio no levantan Redis.
    """
    from src.modules.sales.application import tasks

    venta_id = payload["venta_id"]
    try:
        tasks.programar_revision_demora(venta_id)
    except Exception:
        # Que la cola esté caída no puede tumbar la venta: ya está cobrada y
        # el pedido salió a cocina. El barrido periódico lo levanta igual —
        # para eso existe.
        log.exception(
            "No se pudo programar la revisión de demora", extra={"venta_id": venta_id}
        )


def on_cuenta_registrada(payload: dict) -> None:
    """Una cuenta nueva del sitio de marca se enlaza a un `cliente` de
    `sales` (ADR-104): el sitio no importa `application.clientes` —publica
    el evento y este handler hace la llamada real, mismo patrón que
    `on_entrega_registrada`.

    Sin `marca_id` en el payload (sitio sin marca configurada, no debería
    pasar) o sin poder resolver el grupo, no hay nada que crear: la cuenta
    se queda sin `cliente_id` hasta que alguien la revise a mano — RN-PTS-001
    exige el grupo, y RN-PTS-002 el teléfono o RUC para poder registrar.
    """
    from src.modules.sales.application import clientes
    from src.modules.sales.application.errors import ReglaNegocio
    from src.modules.users.application.queries_publicas import grupo_de_marca

    cuenta_id = payload["cuenta_id"]
    marca_id = payload.get("marca_id")
    if not marca_id:
        log.warning("cuenta_registrada sin marca_id; no se vincula a cliente")
        return

    ubicacion = payload.get("ubicacion") or {}
    try:
        with session_factory() as session:
            grupo_id = grupo_de_marca(session, uuid.UUID(marca_id))
            if grupo_id is None:
                log.warning(
                    "No se pudo resolver el grupo de la marca del sitio",
                    extra={"marca_id": marca_id},
                )
                return
            try:
                cliente = clientes.crear_o_encontrar_cliente(
                    session,
                    grupo_id=grupo_id,
                    nombre=f"{payload['nombres']} {payload['apellidos']}".strip(),
                    telefono=payload.get("telefono"),
                    numero_documento=payload.get("numero_documento"),
                    email=payload.get("email"),
                    direccion=payload.get("direccion"),
                    fecha_nacimiento=(
                        date.fromisoformat(payload["fecha_nacimiento"])
                        if payload.get("fecha_nacimiento")
                        else None
                    ),
                    tipo_documento=payload.get("tipo_documento") or "dni",
                    ubicacion_place_id=ubicacion.get("ubicacion_place_id"),
                    ubicacion_lat=ubicacion.get("ubicacion_lat"),
                    ubicacion_lng=ubicacion.get("ubicacion_lng"),
                    ubicacion_plus_code=ubicacion.get("ubicacion_plus_code"),
                    ubicacion_distrito=ubicacion.get("ubicacion_distrito"),
                )
            except ReglaNegocio:
                # Datos insuficientes para un cliente de `sales` (sin
                # teléfono ni documento, por ejemplo un registro mínimo).
                # La cuenta del sitio sigue funcionando sin `cliente_id`.
                log.info(
                    "Cuenta del sitio sin datos suficientes para vincular cliente",
                    extra={"cuenta_id": cuenta_id},
                )
                return
            # Publicar ANTES del commit (`core/events.py`): el evento se
            # bufferiza en la sesión y recién se despacha en `after_commit`
            # — publicarlo después de commitear no lo despacharía nunca.
            event_bus.publish(
                "sales.cliente_vinculado",
                {"cuenta_id": cuenta_id, "cliente_id": str(cliente.id)},
                session=session,
            )
            session.commit()
    except Exception:
        log.exception(
            "No se pudo vincular la cuenta del sitio a un cliente",
            extra={"cuenta_id": cuenta_id},
        )


def on_entrega_registrada(payload: dict) -> None:
    """`delivery` registró la entrega de una venta: se marca entregada acá,
    con la misma `cumplimiento.registrar_entrega` que usa el botón
    "Entregar" del KDS (ADR-098) — mismo camino, mismo idempotente
    (RN-CUP-005), sin que `sales` sepa que existe `delivery`.

    `entregado_por` es el `repartidor_usuario_id` del payload y no quien
    tocó el botón en el celular: RN-CUP-007 pide registrar **quién
    entrega**, y eso es el repartidor, aunque lo haya confirmado despacho
    en su nombre.

    Fallar acá no deshace la entrega ya registrada en `delivery` (ADR-016,
    entrega best-effort en proceso): queda una venta sin marcar hasta que
    alguien la entregue a mano desde el KDS. Se documenta como costo
    aceptado en `events.md`, no se reintenta desde acá.
    """
    from src.modules.sales.application import cumplimiento

    venta_id = uuid.UUID(payload["venta_id"])
    entregado_por = uuid.UUID(payload["repartidor_usuario_id"])
    try:
        with session_factory() as session:
            cumplimiento.registrar_entrega(session, venta_id, entregado_por=entregado_por)
            session.commit()
    except Exception:
        log.exception(
            "No se pudo marcar entregada la venta de una entrega de delivery",
            extra={"venta_id": str(venta_id)},
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("sales.venta_confirmada", on_venta_confirmada)
    event_bus.subscribe("delivery.entrega_registrada", on_entrega_registrada)
    event_bus.subscribe("storefront.cuenta_registrada", on_cuenta_registrada)
