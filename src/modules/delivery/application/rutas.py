"""Crear y llevar una ruta de reparto de principio a fin (ADR-098).

`crear` y `editar_paradas` comparten la misma validación de qué ventas
pueden entrar a una ruta (`_ventas_para_ruta`): modalidad delivery, sin
plataforma externa (RN-PER-003), no anulada y con dirección anclada al
mapa (RN-DLV-002) — todo leído por el contrato público de `sales`, nunca
importando `Venta`. Una venta se rutea desde que se toma el pedido, esté
o no lista todavía (RN-DLV-001): lo que exige que todas sus paradas estén
`lista` es recién `iniciar`, cuando el repartidor sale a la calle
(RN-DLV-005).
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
from src.modules.users.application.queries_publicas import notificar_a
from src.modules.users.infrastructure.models import Sucursal
from src.shared.auditoria import registrar as auditar
from src.shared.integrations.google import Coordenada

TIPO_RUTA_ASIGNADA = "delivery.ruta_asignada"


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
    if venta["ubicacion_lat"] is None or venta["ubicacion_lng"] is None:
        raise ReglaNegocio("la venta no tiene dirección anclada al mapa")
    return venta


def _sin_entregas_abiertas_en_otra_ruta(
    session: Session, venta_ids: list[uuid.UUID], *, ruta_id_actual: uuid.UUID | None
) -> None:
    ruteadas = EntregaRepo(session).venta_ids_ya_ruteadas(venta_ids)
    if ruta_id_actual is not None:
        # Editando su propia ruta: las entregas que ya son suyas no cuentan
        # como "ya ruteadas en otra parte".
        propias = {e.venta_id for e in EntregaRepo(session).de_ruta(ruta_id_actual)}
        ruteadas -= propias
    if ruteadas:
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


def _origen_de_ruta(session: Session, ruta: RutaReparto) -> Coordenada:
    """Punto de partida para replanificar lo pendiente de una ruta ya
    creada: la última posición conocida del repartidor si la ruta está en
    curso y ya pingueó, la sucursal si no (recién iniciada, o todavía
    planificada)."""
    if ruta.estado == "en_curso" and ruta.ultima_lat is not None and ruta.ultima_lng is not None:
        return Coordenada(lat=ruta.ultima_lat, lng=ruta.ultima_lng)
    return _origen_de_sucursal(session, ruta.sucursal_id)


def _plan_de(
    origen: Coordenada,
    ventas: list[dict],
    *,
    optimizar: bool,
    parametros: ParametrosReparto,
):
    paradas = [Coordenada(lat=v["ubicacion_lat"], lng=v["ubicacion_lng"]) for v in ventas]
    return ruteo.planificar(origen, paradas, optimizar=optimizar, parametros=parametros)


def _asignar_parada(
    session: Session,
    *,
    existente: Entrega | None,
    venta: dict,
    sucursal_id: uuid.UUID,
    ruta_id: uuid.UUID,
    repartidor_id: uuid.UUID,
    orden_parada: int,
    estado: str,
    tramo: ruteo.Tramo,
    eta_at: datetime | None,
    nuevo_ingreso: bool,
) -> Entrega:
    """Asigna una parada a la ruta, reusando la fila que la venta ya tenía
    si existe — `uq_entrega_venta` es una sola fila por venta, nunca una
    segunda (así se reusa la que quedó `pendiente` al cancelar una ruta o
    al sacarla de otra con `editar_paradas`)."""
    entrega = existente
    if entrega is None:
        entrega = Entrega(venta_id=venta["id"], sucursal_id=sucursal_id)
        session.add(entrega)
    entrega.ruta_id = ruta_id
    entrega.repartidor_id = repartidor_id
    entrega.orden_parada = orden_parada
    entrega.estado = estado
    entrega.tramo_distancia_m = tramo.distancia_m
    entrega.tramo_duracion_seg = tramo.duracion_seg
    entrega.destino_lat = venta["ubicacion_lat"]
    entrega.destino_lng = venta["ubicacion_lng"]
    entrega.eta_at = eta_at
    if nuevo_ingreso:
        # RN-DLV-008: token nuevo cuando la parada entra de verdad a la
        # ruta (alta o reingreso), nunca uno heredado de un intento
        # anterior. Una parada que ya estaba en la ruta conserva el enlace
        # que el cliente ya pudo haber recibido por WhatsApp.
        entrega.token_publico = nuevo_token()
        entrega.token_expira_at = None
    return entrega


def _repartidor_para_ruta(
    session: Session, ruta: RutaReparto, repartidor_id: uuid.UUID | None
) -> Repartidor:
    """Repartidor de la ruta tras la edición: el mismo si no se pide
    cambio, o uno nuevo con las mismas validaciones que al crear la ruta
    (activo, de la misma sucursal) — muta `ruta.repartidor_id` y avisa al
    nuevo repartidor si de verdad cambió."""
    if repartidor_id is None or repartidor_id == ruta.repartidor_id:
        actual = session.get(Repartidor, ruta.repartidor_id)
        if actual is None:
            raise NoEncontrado("repartidor no encontrado")
        return actual
    nuevo = session.get(Repartidor, repartidor_id)
    if nuevo is None or nuevo.deleted_at is not None:
        raise NoEncontrado("repartidor no encontrado")
    if not nuevo.activo:
        raise ReglaNegocio("el repartidor no está activo")
    if nuevo.sucursal_id != ruta.sucursal_id:
        raise ReglaNegocio("el repartidor debe ser de la misma sucursal de la ruta")
    ruta.repartidor_id = repartidor_id
    notificar_a(
        session,
        nuevo.usuario_id,
        tipo=TIPO_RUTA_ASIGNADA,
        titulo="Te reasignaron una ruta",
        cuerpo="Te asignaron una ruta de reparto ya en marcha. Revísala desde tu teléfono.",
        sucursal_id=ruta.sucursal_id,
    )
    return nuevo


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
    origen = _origen_de_sucursal(session, sucursal_id)
    plan = _plan_de(origen, ventas, optimizar=optimizar, parametros=parametros)

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

    entrega_repo = EntregaRepo(session)
    for orden_parada, indice in enumerate(plan.orden):
        venta = ventas[indice]
        _asignar_parada(
            session,
            existente=entrega_repo.get_por_venta(venta["id"]),
            venta=venta,
            sucursal_id=sucursal_id,
            ruta_id=ruta.id,
            repartidor_id=repartidor_id,
            orden_parada=orden_parada,
            estado="asignada",
            tramo=plan.tramos[orden_parada],
            eta_at=None,
            nuevo_ingreso=True,
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
    notificar_a(
        session,
        repartidor.usuario_id,
        tipo=TIPO_RUTA_ASIGNADA,
        titulo="Tienes una ruta nueva",
        cuerpo=f"Te asignaron {len(ventas)} entrega(s). Revísala desde tu teléfono.",
        sucursal_id=sucursal_id,
    )
    return ruta


def _resueltas_y_actuales(
    entregas_de_ruta: list[Entrega],
) -> tuple[list[Entrega], dict[uuid.UUID, Entrega]]:
    """Separa las entregas de una ruta en las ya resueltas (fijas, en su
    orden actual) y las demás, indexadas por venta — lo que
    `editar_paradas` necesita para no tocar lo resuelto."""
    resueltas = sorted(
        (e for e in entregas_de_ruta if e.estado in rules.ESTADOS_ENTREGA_RESUELTOS),
        key=lambda e: e.orden_parada if e.orden_parada is not None else 0,
    )
    actuales = {
        e.venta_id: e for e in entregas_de_ruta if e.estado not in rules.ESTADOS_ENTREGA_RESUELTOS
    }
    return resueltas, actuales


def _liberar_no_incluidas(actuales: dict[uuid.UUID, Entrega], venta_ids: list[uuid.UUID]) -> None:
    """Las que ya eran de la ruta y quedan fuera del nuevo conjunto vuelven
    al montón — no se borran ni se marcan como fallidas: simplemente no
    les tocó esta salida (o esta edición)."""
    for venta_id, entrega in actuales.items():
        if venta_id not in venta_ids:
            entrega.estado = "pendiente"
            entrega.ruta_id = None
            entrega.repartidor_id = None
            entrega.orden_parada = None
            entrega.tramo_distancia_m = None
            entrega.tramo_duracion_seg = None
            entrega.eta_at = None


def editar_paradas(
    session: Session,
    ruta_id: uuid.UUID,
    *,
    venta_ids: list[uuid.UUID],
    repartidor_id: uuid.UUID | None,
    optimizar: bool,
    empresa_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> RutaReparto:
    """Reordena, agrega o quita paradas de una ruta ya creada — planificada
    o en curso (RN-DLV-005 extendida) — y opcionalmente le cambia el
    repartidor.

    `venta_ids` es el conjunto de paradas **no resueltas** que se quiere
    después del cambio: una parada `entregada`, `fallida` o `cancelada`
    queda fija (nunca se quita ni se reordena, ver
    `rules.ESTADOS_ENTREGA_RESUELTOS`) y no hace falta repetirla acá — solo
    lo pendiente se replanifica.
    """
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    if not rules.puede_editar_paradas(ruta.estado):
        raise ReglaNegocio("la ruta ya terminó: no se le puede editar paradas")

    resueltas, actuales = _resueltas_y_actuales(EntregaRepo(session).de_ruta(ruta_id))
    if {e.venta_id for e in resueltas} & set(venta_ids):
        raise ReglaNegocio("una de estas paradas ya se resolvió y no puede reingresar a la ruta")

    parametros = parametros_de(session, empresa_id)
    total_paradas = len(resueltas) + len(venta_ids)
    if not rules.cantidad_de_paradas_valida(total_paradas, parametros.max_paradas_ruta):
        raise ReglaNegocio(f"una ruta lleva entre 1 y {parametros.max_paradas_ruta} paradas")

    ventas = _ventas_para_ruta(session, ruta.sucursal_id, venta_ids, ruta_id_actual=ruta_id)
    if ruta.estado == "en_curso":
        no_listas = [v["numero_orden"] for v in ventas if not v["lista"]]
        if no_listas:
            pedidos = ", ".join(f"#{n}" for n in no_listas)
            raise ReglaNegocio(
                f"la ruta ya salió: no se le agregan pedidos que siguen en cocina ({pedidos})"
            )

    repartidor = _repartidor_para_ruta(session, ruta, repartidor_id)
    _liberar_no_incluidas(actuales, venta_ids)

    origen = _origen_de_ruta(session, ruta)
    plan = _plan_de(origen, ventas, optimizar=optimizar, parametros=parametros)

    en_curso = ruta.estado == "en_curso"
    ahora = datetime.now(UTC) if en_curso else None
    etas = rules.eta_por_parada(ahora, [t.duracion_seg for t in plan.tramos]) if ahora else None

    entrega_repo = EntregaRepo(session)
    inicio = len(resueltas)
    for posicion, indice in enumerate(plan.orden):
        venta = ventas[indice]
        entrega = actuales.get(venta["id"]) or entrega_repo.get_por_venta(venta["id"])
        _asignar_parada(
            session,
            existente=entrega,
            venta=venta,
            sucursal_id=ruta.sucursal_id,
            ruta_id=ruta.id,
            repartidor_id=repartidor.id,
            orden_parada=inicio + posicion,
            estado="en_ruta" if en_curso else "asignada",
            tramo=plan.tramos[posicion],
            eta_at=etas[posicion] if etas else None,
            nuevo_ingreso=venta["id"] not in actuales,
        )

    # Las resueltas quedan fijas en todo salvo el número de parada: se
    # renumeran al inicio, contiguas y en su orden relativo, para que no
    # queden huecos si alguna parada se sacó de la ruta en una edición
    # anterior.
    for posicion, entrega in enumerate(resueltas):
        entrega.orden_parada = posicion

    ruta.distancia_m = sum(e.tramo_distancia_m or 0 for e in resueltas) + plan.distancia_m
    ruta.duracion_seg = sum(e.tramo_duracion_seg or 0 for e in resueltas) + plan.duracion_seg
    ruta.polyline = plan.polyline
    ruta.optimizada_por = plan.fuente
    session.flush()

    auditar(
        session,
        entidad="ruta_reparto",
        accion="editar_paradas",
        entidad_id=ruta.id,
        usuario_id=actor_id,
        datos_despues={
            "paradas_pendientes": str(len(ventas)),
            "repartidor_id": str(repartidor.id),
        },
        empresa_id=empresa_id,
        sucursal_id=ruta.sucursal_id,
    )
    return ruta


def _paradas_no_listas(session: Session, entregas: list[Entrega]) -> list[int]:
    """Números de orden de las paradas cuyo pedido todavía no está en
    `listo`/`entregado` (RN-DLV-005): una ruta se planifica con pedidos en
    cocina, pero no sale con uno a medio preparar — el repartidor no espera
    en la puerta."""
    numeros = []
    for entrega in entregas:
        venta = venta_para_reparto(session, entrega.venta_id)
        if venta is not None and not venta["lista"]:
            numeros.append(venta["numero_orden"])
    return numeros


def iniciar(session: Session, ruta_id: uuid.UUID, *, actor_id: uuid.UUID) -> RutaReparto:
    ruta = session.get(RutaReparto, ruta_id)
    if ruta is None:
        raise NoEncontrado("ruta no encontrada")
    entregas = EntregaRepo(session).de_ruta(ruta_id)
    if not rules.puede_iniciar_ruta(ruta.estado, len(entregas)):
        raise ReglaNegocio("la ruta necesita al menos una parada y estar planificada")
    no_listas = _paradas_no_listas(session, entregas)
    if no_listas:
        pedidos = ", ".join(f"#{n}" for n in no_listas)
        raise ReglaNegocio(f"hay pedidos que siguen en cocina: {pedidos}")
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
