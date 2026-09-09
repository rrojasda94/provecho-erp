"""Crear y llevar una ruta de reparto de principio a fin (ADR-098).

`crear` y `editar_paradas` comparten la misma validación de qué ventas
pueden entrar a una ruta (`_ventas_para_ruta`): modalidad delivery, sin
plataforma externa (RN-PER-003), no anuladas, listas para salir y con
dirección anclada al mapa (RN-DLV-002) — todo leído por el contrato
público de `sales`, nunca importando `Venta`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.delivery.application import ruteo
from src.modules.delivery.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.delivery.application.parametros import ParametrosReparto, parametros_de
from src.modules.delivery.application.seguimiento import nuevo_token
from src.modules.delivery.domain import rules
from src.modules.delivery.infrastructure.models import Entrega, Repartidor, RutaReparto
from src.modules.delivery.infrastructure.repositories import EntregaRepo, RutaRepo
from src.modules.sales.application.queries_publicas import venta_para_reparto
from src.modules.users.infrastructure.models import Sucursal
from src.shared.auditoria import registrar as auditar
from src.shared.integrations.google import Coordenada


def _validar_venta_para_ruta(
    venta: dict | None, venta_id: uuid.UUID, sucursal_id: uuid.UUID
) -> dict:
    if venta is None:
        raise NoEncontrado(f"venta no encontrada: {venta_id}")
    if venta["sucursal_id"] != sucursal_id:
        raise ReglaNegocio("todas las ventas deben ser de la misma sucursal de la ruta")
    if venta["modalidad"] != "delivery":
        raise ReglaNegocio("solo se rutean ventas en modalidad delivery")
    if venta["repartidor_externo_plataforma"]:
        raise ReglaNegocio("esta venta ya va por una plataforma externa")
    if venta["estado"] == "anulada":
        raise Conflicto("la venta está anulada")
    if not venta["lista"]:
        raise ReglaNegocio("la venta todavía no está lista para salir")
    if venta["ubicacion_lat"] is None or venta["ubicacion_lng"] is None:
        raise ReglaNegocio("la venta no tiene dirección anclada al mapa")
    return venta


def _sin_entregas_abiertas_en_otra_ruta(
    session: Session, venta_ids: list[uuid.UUID], *, ruta_id_actual: uuid.UUID | None
) -> None:
    abiertas = EntregaRepo(session).venta_ids_con_entrega_abierta(venta_ids)
    if ruta_id_actual is not None:
        # Editando su propia ruta: las entregas que ya son suyas no cuentan
        # como "ya abiertas en otra parte".
        propias = {e.venta_id for e in EntregaRepo(session).de_ruta(ruta_id_actual)}
        abiertas -= propias
    if abiertas:
        raise Conflicto("una de estas ventas ya tiene una entrega en curso")


def _ventas_para_ruta(
    session: Session,
    sucursal_id: uuid.UUID,
    venta_ids: list[uuid.UUID],
    *,
    ruta_id_actual: uuid.UUID | None = None,
) -> list[dict]:
    if len(set(venta_ids)) != len(venta_ids):
        raise ReglaNegocio("una venta no puede repetirse en la misma ruta")
    _sin_entregas_abiertas_en_otra_ruta(session, venta_ids, ruta_id_actual=ruta_id_actual)
    return [
        _validar_venta_para_ruta(venta_para_reparto(session, venta_id), venta_id, sucursal_id)
        for venta_id in venta_ids
    ]


def _origen_de_sucursal(session: Session, sucursal_id: uuid.UUID) -> Coordenada:
    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None:
        raise NoEncontrado("sucursal no encontrada")
    if sucursal.ubicacion_lat is None or sucursal.ubicacion_lng is None:
        raise ReglaNegocio("la sucursal no tiene ubicación anclada al mapa")
    return Coordenada(lat=sucursal.ubicacion_lat, lng=sucursal.ubicacion_lng)


def _plan_de(
    session: Session,
    sucursal_id: uuid.UUID,
    ventas: list[dict],
    *,
    optimizar: bool,
    parametros: ParametrosReparto,
):
    origen = _origen_de_sucursal(session, sucursal_id)
    paradas = [Coordenada(lat=v["ubicacion_lat"], lng=v["ubicacion_lng"]) for v in ventas]
    return origen, ruteo.planificar(origen, paradas, optimizar=optimizar, parametros=parametros)


def crear(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    sucursal_id: uuid.UUID,
    repartidor_id: uuid.UUID,
    venta_ids: list[uuid.UUID],
    optimizar: bool,
    creada_por: uuid.UUID,
) -> RutaReparto:
    repartidor = session.get(Repartidor, repartidor_id)
    if repartidor is None or repartidor.deleted_at is not None:
        raise NoEncontrado("repartidor no encontrado")
    if not repartidor.activo:
        raise ReglaNegocio("el repartidor no está activo")

    parametros = parametros_de(session, empresa_id)
    if not rules.cantidad_de_paradas_valida(len(venta_ids), parametros.max_paradas_ruta):
        raise ReglaNegocio(f"una ruta lleva entre 1 y {parametros.max_paradas_ruta} paradas")

    ventas = _ventas_para_ruta(session, sucursal_id, venta_ids)
    origen, plan = _plan_de(
        session, sucursal_id, ventas, optimizar=optimizar, parametros=parametros
    )

    ruta = RutaReparto(
        sucursal_id=sucursal_id,
        repartidor_id=repartidor_id,
        creada_por=creada_por,
        estado="planificada",
        origen_lat=origen.lat,
        origen_lng=origen.lng,
        distancia_m=plan.distancia_m,
        duracion_seg=plan.duracion_seg,
        polyline=plan.polyline,
        optimizada_por=plan.fuente,
    )
    session.add(ruta)
    session.flush()

    for orden_parada, indice in enumerate(plan.orden):
        venta = ventas[indice]
        tramo = plan.tramos[orden_parada]
        session.add(
            Entrega(
                venta_id=venta["id"],
                sucursal_id=sucursal_id,
                ruta_id=ruta.id,
                repartidor_id=repartidor_id,
                orden_parada=orden_parada,
                estado="asignada",
                tramo_distancia_m=tramo.distancia_m,
                tramo_duracion_seg=tramo.duracion_seg,
                destino_lat=venta["ubicacion_lat"],
                destino_lng=venta["ubicacion_lng"],
                # RN-DLV-008: token nuevo en cada asignación, nunca uno
                # heredado de un intento anterior.
                token_publico=nuevo_token(),
            )
        )
    session.flush()

    auditar(
        session,
        entidad="ruta_reparto",
        accion="crear",
        entidad_id=ruta.id,
        usuario_id=creada_por,
        datos_despues={
            "repartidor_id": str(repartidor_id),
            "paradas": str(len(ventas)),
            "optimizada_por": plan.fuente,
        },
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
    )
    return ruta


def editar_paradas(
    session: Session,
    ruta_id: uuid.UUID,
    *,
    venta_ids: list[uuid.UUID],
    optimizar: bool,
    empresa_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> RutaReparto:
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    if not rules.puede_editar_paradas(ruta.estado):
        raise ReglaNegocio("la ruta ya salió o terminó: no se le puede editar paradas")

    parametros = parametros_de(session, empresa_id)
    if not rules.cantidad_de_paradas_valida(len(venta_ids), parametros.max_paradas_ruta):
        raise ReglaNegocio(f"una ruta lleva entre 1 y {parametros.max_paradas_ruta} paradas")

    ventas = _ventas_para_ruta(session, ruta.sucursal_id, venta_ids, ruta_id_actual=ruta_id)

    # Las entregas que ya eran de esta ruta y quedan fuera del nuevo
    # conjunto vuelven al montón de pendientes — no se borran ni se
    # marcan como fallidas: simplemente no les tocó esta salida.
    actuales = {e.venta_id: e for e in EntregaRepo(session).de_ruta(ruta_id)}
    for venta_id, entrega in actuales.items():
        if venta_id not in venta_ids:
            entrega.estado = "pendiente"
            entrega.ruta_id = None
            entrega.repartidor_id = None
            entrega.orden_parada = None
            entrega.tramo_distancia_m = None
            entrega.tramo_duracion_seg = None
            entrega.eta_at = None

    _origen, plan = _plan_de(
        session, ruta.sucursal_id, ventas, optimizar=optimizar, parametros=parametros
    )
    ruta.distancia_m = plan.distancia_m
    ruta.duracion_seg = plan.duracion_seg
    ruta.polyline = plan.polyline
    ruta.optimizada_por = plan.fuente

    for orden_parada, indice in enumerate(plan.orden):
        venta = ventas[indice]
        tramo = plan.tramos[orden_parada]
        entrega = actuales.get(venta["id"])
        if entrega is None:
            entrega = Entrega(venta_id=venta["id"], sucursal_id=ruta.sucursal_id)
            session.add(entrega)
        entrega.ruta_id = ruta.id
        entrega.repartidor_id = ruta.repartidor_id
        entrega.orden_parada = orden_parada
        entrega.estado = "asignada"
        entrega.tramo_distancia_m = tramo.distancia_m
        entrega.tramo_duracion_seg = tramo.duracion_seg
        entrega.destino_lat = venta["ubicacion_lat"]
        entrega.destino_lng = venta["ubicacion_lng"]
        # RN-DLV-008: token nuevo en cada asignación (alta o reingreso a
        # una ruta), nunca uno heredado de un intento anterior.
        entrega.token_publico = nuevo_token()
        entrega.token_expira_at = None
    session.flush()

    auditar(
        session,
        entidad="ruta_reparto",
        accion="editar_paradas",
        entidad_id=ruta.id,
        usuario_id=actor_id,
        datos_despues={"paradas": str(len(ventas))},
        empresa_id=empresa_id,
        sucursal_id=ruta.sucursal_id,
    )
    return ruta


def iniciar(session: Session, ruta_id: uuid.UUID, *, actor_id: uuid.UUID) -> RutaReparto:
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    entregas = EntregaRepo(session).de_ruta(ruta_id)
    if not rules.puede_iniciar_ruta(ruta.estado, len(entregas)):
        raise ReglaNegocio("la ruta necesita al menos una parada y estar planificada")
    repartidor = session.get(Repartidor, ruta.repartidor_id)
    if repartidor is None or not repartidor.activo:
        raise ReglaNegocio("el repartidor no está activo")

    ahora = datetime.now(UTC)
    ruta.estado = "en_curso"
    ruta.hora_salida = ahora
    etas = rules.eta_por_parada(ahora, [e.tramo_duracion_seg or 0 for e in entregas])
    for entrega, eta in zip(entregas, etas, strict=True):
        entrega.estado = "en_ruta"
        entrega.eta_at = eta
    session.flush()

    auditar(
        session,
        entidad="ruta_reparto",
        accion="iniciar",
        entidad_id=ruta.id,
        usuario_id=actor_id,
        sucursal_id=ruta.sucursal_id,
    )
    event_bus.publish(
        "delivery.ruta_iniciada",
        {
            "ruta_id": str(ruta.id),
            "sucursal_id": str(ruta.sucursal_id),
            "repartidor_id": str(ruta.repartidor_id),
            "entrega_ids": [str(e.id) for e in entregas],
            "venta_ids": [str(e.venta_id) for e in entregas],
        },
        session=session,
    )
    return ruta


def finalizar(session: Session, ruta_id: uuid.UUID, *, actor_id: uuid.UUID) -> RutaReparto:
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    entregas = EntregaRepo(session).de_ruta(ruta_id)
    estados = [e.estado for e in entregas]
    if not rules.puede_finalizar_ruta(ruta.estado, estados):
        raise Conflicto("quedan paradas sin resolver")

    ruta.estado = "finalizada"
    ruta.hora_fin = datetime.now(UTC)
    session.flush()

    auditar(
        session,
        entidad="ruta_reparto",
        accion="finalizar",
        entidad_id=ruta.id,
        usuario_id=actor_id,
        sucursal_id=ruta.sucursal_id,
    )
    event_bus.publish(
        "delivery.ruta_finalizada",
        {
            "ruta_id": str(ruta.id),
            "sucursal_id": str(ruta.sucursal_id),
            "repartidor_id": str(ruta.repartidor_id),
            "distancia_m": ruta.distancia_m,
            "duracion_seg": ruta.duracion_seg,
            "entregadas": sum(1 for e in estados if e == "entregada"),
            "fallidas": sum(1 for e in estados if e == "fallida"),
        },
        session=session,
    )
    return ruta


def cancelar(session: Session, ruta_id: uuid.UUID, *, actor_id: uuid.UUID) -> RutaReparto:
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    if not rules.puede_cancelar_ruta(ruta.estado):
        raise Conflicto("solo se cancela una ruta planificada")

    for entrega in EntregaRepo(session).de_ruta(ruta_id):
        entrega.estado = "pendiente"
        entrega.ruta_id = None
        entrega.repartidor_id = None
        entrega.orden_parada = None
        entrega.tramo_distancia_m = None
        entrega.tramo_duracion_seg = None
        entrega.eta_at = None
    ruta.estado = "cancelada"
    session.flush()

    auditar(
        session,
        entidad="ruta_reparto",
        accion="cancelar",
        entidad_id=ruta.id,
        usuario_id=actor_id,
        sucursal_id=ruta.sucursal_id,
    )
    return ruta


def q_list(
    session: Session,
    sucursal_ids: list[uuid.UUID] | None = None,
    *,
    estado: str | None = None,
):
    return RutaRepo(session).q_list(sucursal_ids, estado=estado)


def mis_rutas(session: Session, repartidor_id: uuid.UUID) -> list[RutaReparto]:
    return RutaRepo(session).vivas_de_repartidor(repartidor_id)
