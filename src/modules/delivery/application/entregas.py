"""Registrar el resultado de una entrega: entregada, fallida, reintentada
o cerrada (ADR-098) — la rama delivery de `PROC-OPE-002` que
`sales.application.cumplimiento` no cubre.

Entregar y fallar publican evento; reintentar y cerrar no —no son un
hecho que otro módulo necesite saber, son la vuelta al tablero de algo que
`sales` nunca llegó a enterarse que había fallado.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.delivery.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.delivery.application.seguimiento import token_expira_en
from src.modules.delivery.domain import rules
from src.modules.delivery.infrastructure.models import Entrega, Repartidor, RutaReparto
from src.modules.delivery.infrastructure.repositories import EntregaRepo
from src.modules.rrhh.application.queries_publicas import cuenta_de_trabajador
from src.modules.sales.application.queries_publicas import (
    contacto_de_cliente,
    venta_para_reparto,
)
from src.modules.users.application.queries_publicas import notificar_a
from src.shared.auditoria import registrar as auditar

# Códigos de `notificacion.tipo` (bandeja in-app, `users.notificar_a`).
TIPO_ENTREGA_FALLIDA = "delivery.entrega_fallida"
TIPO_VENTA_ANULADA_EN_RUTA = "delivery.venta_anulada_en_ruta"


def entregar(
    session: Session,
    entrega_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    lat: Decimal | None = None,
    lng: Decimal | None = None,
    foto: bytes | None = None,
    observacion: str | None = None,
) -> Entrega:
    entrega = EntregaRepo(session).get(entrega_id)
    if entrega is None:
        raise NoEncontrado("entrega no encontrada")
    if entrega.estado == "entregada":
        # Idempotente, mismo criterio que `sales.cumplimiento.registrar_entrega`
        # (RN-CUP-005): repetir la entrega no vuelve a emitir el evento.
        return entrega
    if not rules.puede_entregar(entrega.estado):
        raise ReglaNegocio("la entrega no está en ruta")
    repartidor = session.get(Repartidor, entrega.repartidor_id)
    if repartidor is None:
        raise Conflicto("la entrega no tiene repartidor asignado")

    ahora = datetime.now(UTC)
    antes = {"estado": entrega.estado}
    entrega.estado = "entregada"
    entrega.fecha_entrega = ahora
    # RN-CUP-007: se registra quién entrega — el repartidor, no
    # necesariamente quien tocó el botón (puede ser despacho, en su
    # nombre). Quién lo tocó de verdad queda en el `audit_log`.
    entrega.entregado_por = repartidor.usuario_id
    entrega.resultado_lat = lat
    entrega.resultado_lng = lng
    # RN-DLV-008: el enlace público sigue vivo unas horas más después del
    # resultado, no se apaga de golpe (el cliente todavía puede querer ver
    # que llegó).
    entrega.token_expira_at = token_expira_en(ahora)
    if foto is not None:
        entrega.evidencia_foto = foto
    if observacion is not None:
        entrega.observacion = observacion
    session.flush()

    auditar(
        session,
        entidad="entrega",
        accion="entregar",
        entidad_id=entrega.id,
        usuario_id=actor_id,
        datos_antes=antes,
        datos_despues={"estado": "entregada"},
        sucursal_id=entrega.sucursal_id,
    )
    event_bus.publish(
        "delivery.entrega_registrada",
        {
            "entrega_id": str(entrega.id),
            "venta_id": str(entrega.venta_id),
            "sucursal_id": str(entrega.sucursal_id),
            "ruta_id": str(entrega.ruta_id) if entrega.ruta_id else None,
            "repartidor_id": str(entrega.repartidor_id),
            "repartidor_usuario_id": str(repartidor.usuario_id),
            "fecha_entrega": ahora.isoformat(),
        },
        session=session,
    )
    return entrega


def fallar(
    session: Session,
    entrega_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    motivo: str,
    detalle: str | None = None,
    lat: Decimal | None = None,
    lng: Decimal | None = None,
    foto: bytes | None = None,
) -> Entrega:
    if motivo not in rules.MOTIVOS_FALLO:
        raise ReglaNegocio(f"motivo de fallo desconocido: {motivo}")
    if rules.motivo_requiere_detalle(motivo) and not detalle:
        raise ReglaNegocio('el motivo "otro" exige un detalle (RN-DLV-003)')

    entrega = EntregaRepo(session).get(entrega_id)
    if entrega is None:
        raise NoEncontrado("entrega no encontrada")
    if not rules.puede_fallar(entrega.estado):
        raise ReglaNegocio("la entrega no está en ruta")

    antes = {"estado": entrega.estado}
    entrega.estado = "fallida"
    entrega.motivo_fallo = motivo
    entrega.motivo_detalle = detalle
    entrega.resultado_lat = lat
    entrega.resultado_lng = lng
    entrega.token_expira_at = token_expira_en()
    if foto is not None:
        entrega.evidencia_foto = foto
    session.flush()

    auditar(
        session,
        entidad="entrega",
        accion="fallar",
        entidad_id=entrega.id,
        usuario_id=actor_id,
        datos_antes=antes,
        datos_despues={"estado": "fallida", "motivo_fallo": motivo},
        sucursal_id=entrega.sucursal_id,
    )
    event_bus.publish(
        "delivery.entrega_fallida",
        {
            "entrega_id": str(entrega.id),
            "venta_id": str(entrega.venta_id),
            "sucursal_id": str(entrega.sucursal_id),
            "ruta_id": str(entrega.ruta_id) if entrega.ruta_id else None,
            "repartidor_id": str(entrega.repartidor_id),
            "motivo": motivo,
            "intento": entrega.intentos,
        },
        session=session,
    )
    _avisar_a_quien_creo_la_ruta(
        session,
        entrega,
        tipo=TIPO_ENTREGA_FALLIDA,
        titulo="Una entrega falló",
        cuerpo=f"El pedido no se pudo entregar. Motivo: {motivo}.",
    )
    return entrega


def reintentar(session: Session, entrega_id: uuid.UUID, *, actor_id: uuid.UUID) -> Entrega:
    """RN-DLV-004: vuelve la misma fila a `pendiente` — no crea una entrega
    nueva — y desprende la ruta/parada de la que colgaba: el reintento sale
    en una salida nueva, no reaparece mágicamente en la que ya se cerró."""
    entrega = EntregaRepo(session).get(entrega_id)
    if entrega is None:
        raise NoEncontrado("entrega no encontrada")
    if not rules.puede_reintentar(entrega.estado):
        raise ReglaNegocio("solo se reintenta una entrega fallida")

    antes = {"estado": entrega.estado, "motivo_fallo": entrega.motivo_fallo}
    entrega.estado = "pendiente"
    entrega.intentos += 1
    entrega.motivo_fallo = None
    entrega.motivo_detalle = None
    entrega.ruta_id = None
    entrega.repartidor_id = None
    entrega.orden_parada = None
    entrega.tramo_distancia_m = None
    entrega.tramo_duracion_seg = None
    entrega.eta_at = None
    session.flush()

    auditar(
        session,
        entidad="entrega",
        accion="reintentar",
        entidad_id=entrega.id,
        usuario_id=actor_id,
        datos_antes=antes,
        datos_despues={"estado": "pendiente", "intentos": entrega.intentos},
        sucursal_id=entrega.sucursal_id,
    )
    return entrega


def cerrar(session: Session, entrega_id: uuid.UUID, *, actor_id: uuid.UUID) -> Entrega:
    """Cierra sin reintentar: el encargado decidió que no hay segunda
    vuelta para este pedido (RN-CUP-008 — devolución o merma se resuelven
    por su propia vía, no acá)."""
    entrega = EntregaRepo(session).get(entrega_id)
    if entrega is None:
        raise NoEncontrado("entrega no encontrada")
    if not rules.puede_cerrar_entrega(entrega.estado):
        raise ReglaNegocio("solo se cierra una entrega pendiente o fallida")

    antes = {"estado": entrega.estado}
    entrega.estado = "cancelada"
    entrega.token_expira_at = token_expira_en()
    session.flush()

    auditar(
        session,
        entidad="entrega",
        accion="cerrar",
        entidad_id=entrega.id,
        usuario_id=actor_id,
        datos_antes=antes,
        datos_despues={"estado": "cancelada"},
        sucursal_id=entrega.sucursal_id,
    )
    return entrega


def cerrar_por_venta_entregada(
    session: Session, venta_id: uuid.UUID, *, entregado_por: uuid.UUID | None
) -> None:
    """`sales.venta_entregada` llegó por el KDS, no por el tablero de
    reparto: si había una `entrega` abierta, se cierra sola (ADR-098) —
    los dos caminos convergen sin que ninguno importe al otro."""
    entrega = EntregaRepo(session).get_por_venta(venta_id)
    if entrega is None or entrega.estado in ("entregada", "cancelada"):
        return
    ahora = datetime.now(UTC)
    entrega.estado = "entregada"
    entrega.fecha_entrega = ahora
    entrega.entregado_por = entregado_por
    entrega.token_expira_at = token_expira_en(ahora)
    session.flush()


def cancelar_por_venta_anulada(session: Session, venta_id: uuid.UUID) -> None:
    """RN-DLV-006: si la entrega seguía `pendiente`/`asignada`, se cancela
    sola. `en_ruta` no se toca acá — el repartidor puede estar a mitad de
    camino y lo decide el despacho, no un evento — pero sí avisa in-app a
    quien despachó la ruta: alguien tiene que decidir qué hacer con un
    pedido anulado que ya salió a la calle."""
    entrega = EntregaRepo(session).get_por_venta(venta_id)
    if entrega is None:
        return
    if entrega.estado == "en_ruta":
        _avisar_a_quien_creo_la_ruta(
            session,
            entrega,
            tipo=TIPO_VENTA_ANULADA_EN_RUTA,
            titulo="Una venta en reparto se anuló",
            cuerpo="El pedido ya salió con el repartidor y su venta se anuló. Decide qué hacer.",
        )
        return
    if not rules.cancela_sola_por_anulacion(entrega.estado):
        return
    entrega.estado = "cancelada"
    entrega.token_expira_at = token_expira_en()
    session.flush()


def _avisar_a_quien_creo_la_ruta(
    session: Session, entrega: Entrega, *, tipo: str, titulo: str, cuerpo: str
) -> None:
    if entrega.ruta_id is None:
        return
    ruta = session.get(RutaReparto, entrega.ruta_id)
    if ruta is None:
        return
    notificar_a(
        session,
        ruta.creada_por,
        tipo=tipo,
        titulo=titulo,
        cuerpo=cuerpo,
        sucursal_id=entrega.sucursal_id,
    )


def historial_enriquecido(session: Session, pagina: dict) -> dict:
    """La misma página que arma `paginar()` para `GET /delivery/entregas`,
    con la venta y el repartidor ya resueltos — el historial no llama a
    `sales` ni a `rrhh` por su cuenta (mismo criterio que
    `mi_reparto.ruta_con_paradas`)."""
    pagina["items"] = [_con_venta_y_repartidor(session, e) for e in pagina["items"]]
    return pagina


def _nombre_repartidor(session: Session, repartidor_id: uuid.UUID | None) -> str | None:
    if repartidor_id is None:
        return None
    repartidor = session.get(Repartidor, repartidor_id)
    if repartidor is None:
        return None
    cuenta = cuenta_de_trabajador(session, repartidor.trabajador_id)
    return cuenta["nombre"] if cuenta else None


def _con_venta_y_repartidor(session: Session, entrega: Entrega) -> dict:
    venta = venta_para_reparto(session, entrega.venta_id)
    contacto = (
        contacto_de_cliente(session, venta["cliente_id"])
        if venta and venta["cliente_id"]
        else None
    )
    return {
        "id": entrega.id,
        "venta_id": entrega.venta_id,
        "sucursal_id": entrega.sucursal_id,
        "ruta_id": entrega.ruta_id,
        "repartidor_id": entrega.repartidor_id,
        "repartidor_nombre": _nombre_repartidor(session, entrega.repartidor_id),
        "orden_parada": entrega.orden_parada,
        "estado": entrega.estado,
        "intentos": entrega.intentos,
        "eta_at": entrega.eta_at,
        "tramo_distancia_m": entrega.tramo_distancia_m,
        "tramo_duracion_seg": entrega.tramo_duracion_seg,
        "destino_lat": entrega.destino_lat,
        "destino_lng": entrega.destino_lng,
        "numero_orden": venta["numero_orden"] if venta else None,
        "direccion_entrega": venta["direccion_entrega"] if venta else None,
        "cliente_nombre": contacto["nombre"] if contacto else None,
        "fecha_entrega": entrega.fecha_entrega,
        "entregado_por": entrega.entregado_por,
        "motivo_fallo": entrega.motivo_fallo,
        "motivo_detalle": entrega.motivo_detalle,
        "resultado_lat": entrega.resultado_lat,
        "resultado_lng": entrega.resultado_lng,
        "observacion": entrega.observacion,
    }
