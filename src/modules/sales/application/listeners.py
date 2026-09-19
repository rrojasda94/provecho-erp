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


def _medio_pago_izipay(session, sucursal_id: uuid.UUID) -> uuid.UUID:
    """El medio de pago 'Izipay' de la empresa de esa sucursal, creándolo la
    primera vez que hace falta (ADR-105) — igual que el usuario de servicio
    del sitio, exigir un alta manual antes del primer pedido pagado en
    línea sería un paso de despliegue más para olvidar."""
    from sqlalchemy import func, select

    from src.modules.sales.application import catalogo
    from src.modules.sales.infrastructure.models import MedioPago
    from src.modules.users.infrastructure.models import Sucursal

    sucursal = session.get(Sucursal, sucursal_id)
    existente = session.scalar(
        select(MedioPago).where(
            MedioPago.empresa_id == sucursal.empresa_id,
            func.lower(MedioPago.nombre) == "izipay",
        )
    )
    if existente is not None:
        return existente.id
    creado = catalogo.crear_medio_pago(
        session,
        empresa_id=sucursal.empresa_id,
        nombre="Izipay",
        direccion="cobro",
        tipo="billetera_digital",
    )
    return creado.id


def on_pedido_web_confirmado(payload: dict) -> None:
    """Un pedido confirmado en el sitio de marca (ADR-105) se
    convierte en una `Venta` real de canal `web` — el sitio no importa
    `application.ventas`, publica el evento y este handler hace la llamada
    real, mismo patrón que `on_cuenta_registrada`.

    Efectivo: la venta queda `orden` y se cobra al entregar/recoger, como
    cualquier delivery telefónico — no hay pago que registrar acá.

    Izipay: se cobra de inmediato contra la pasarela activa (`IzipayFake`
    hoy, aprueba siempre) y se registra el pago **sin exigir caja abierta**
    — excepción explícita a RN-POS-005/ADR-025 documentada en ADR-105: en
    delivery/recojo web alguien SÍ cobra en el momento de la entrega (el
    repartidor o el mostrador), la misma garantía que un cajero, así que la
    razón de ser de "cobra por adelantado" (nadie persigue al cliente) no
    aplica igual que en un kiosko de autoservicio dentro del local.

    Si `crear_venta` falla (canal cerrado, producto ya no existe, etc.) el
    pedido del sitio queda `fallido` con el motivo — nunca se reintenta
    solo, el cliente tiene que volver a intentar desde el sitio.
    """
    from decimal import Decimal

    from src.modules.sales.application import ventas
    from src.modules.sales.application.errors import AppError
    from src.modules.users.application.queries_publicas import (
        usuario_servicio_storefront,
    )

    pedido_id = payload["pedido_id"]
    ubicacion = payload.get("ubicacion") or {}
    try:
        with session_factory() as session:
            usuario_id = usuario_servicio_storefront(session)
            try:
                venta = ventas.crear_venta(
                    session,
                    sucursal_id=uuid.UUID(payload["sucursal_id"]),
                    punto_venta_id=uuid.UUID(payload["punto_venta_id"]),
                    canal="web",
                    modalidad=payload["modalidad"],
                    usuario_id=usuario_id,
                    idempotency_key=payload["idempotency_key"],
                    items=[
                        {
                            "producto_comercial_id": uuid.UUID(i["producto_comercial_id"]),
                            "cantidad": i["cantidad"],
                        }
                        for i in payload["items"]
                    ],
                    cliente_id=(
                        uuid.UUID(payload["cliente_id"]) if payload.get("cliente_id") else None
                    ),
                    referencia_atencion=payload.get("nombre_contacto"),
                    direccion_entrega=payload.get("direccion_entrega"),
                    ubicacion_place_id=ubicacion.get("ubicacion_place_id"),
                    ubicacion_lat=(
                        Decimal(ubicacion["ubicacion_lat"])
                        if ubicacion.get("ubicacion_lat")
                        else None
                    ),
                    ubicacion_lng=(
                        Decimal(ubicacion["ubicacion_lng"])
                        if ubicacion.get("ubicacion_lng")
                        else None
                    ),
                    ubicacion_plus_code=ubicacion.get("ubicacion_plus_code"),
                    ubicacion_distrito=ubicacion.get("ubicacion_distrito"),
                    distancia_entrega_km=(
                        Decimal(payload["distancia_entrega_km"])
                        if payload.get("distancia_entrega_km")
                        else None
                    ),
                    costo_entrega=(
                        Decimal(payload["costo_entrega"])
                        if payload.get("costo_entrega")
                        else None
                    ),
                )
            except AppError as e:
                event_bus.publish(
                    "sales.pedido_web_procesado",
                    {"pedido_id": pedido_id, "ok": False, "motivo": str(e)},
                    session=session,
                )
                session.commit()
                return

            # Con Izipay la venta se crea DESPUÉS de que la pasarela aprobó el
            # pago (el webhook dispara este evento), así que acá solo se
            # registra lo ya cobrado. Sin `pago_id_externo` (efectivo) la
            # venta queda por cobrar al entregar/recoger.
            if payload.get("pago_id_externo"):
                try:
                    ventas.registrar_pago(
                        session,
                        venta_id=venta.id,
                        medio_pago_id=_medio_pago_izipay(session, venta.sucursal_id),
                        monto=venta.total,
                        idempotency_key=f"{payload['idempotency_key']}:pago",
                        referencia_externa=payload["pago_id_externo"],
                        receptor_num_doc=payload.get("numero_documento"),
                        receptor_nombre=payload.get("nombre_o_razon_social"),
                        exigir_caja_abierta=False,
                    )
                except AppError:
                    # La venta ya existe y sale a cocina igual; el cobro se
                    # revisa a mano. No se le informa "fallido" al sitio por
                    # esto — el pedido SÍ se va a preparar.
                    log.exception(
                        "No se pudo registrar el pago Izipay de un pedido web",
                        extra={"venta_id": str(venta.id)},
                    )

            event_bus.publish(
                "sales.pedido_web_procesado",
                {
                    "pedido_id": pedido_id,
                    "ok": True,
                    "venta_id": str(venta.id),
                    "numero_orden": venta.numero_orden,
                },
                session=session,
            )
            session.commit()
    except Exception:
        log.exception(
            "No se pudo procesar el pedido web", extra={"pedido_id": pedido_id}
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
    event_bus.subscribe("storefront.pedido_web_confirmado", on_pedido_web_confirmado)
