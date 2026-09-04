"""Casos de uso de solicitud de insumos: el local pide, el supervisor
aprueba (RN-INV-001, RN-INV-010, RN-DOC-005).

Ciclo: `borrador` (la lista que el turno junta durante la jornada) →
`pendiente` → `aprobada` | `rechazada` | `cancelada` → (el despacho la
lleva a) `despachada` → `recibida`.

Aprobar **reserva** el stock en el almacén abastecedor: entre que el
supervisor aprueba y el central arma el picking pasan horas, y sin reserva
otra sucursal se lleva lo mismo. Cancelar o rechazar lo suelta.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.inventory.application import reservas as reservas_uc
from src.modules.inventory.application.errors import (
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import (
    SolicitudInsumos,
    SolicitudItem,
)
from src.modules.inventory.infrastructure.repositories import (
    SkuRepo,
    SolicitudRepo,
    StockRepo,
)
from src.modules.users.infrastructure.models import Almacen


def _vigente(session: Session, almacen_id: uuid.UUID | None) -> Almacen | None:
    """El almacén, si existe y no está dado de baja."""
    if almacen_id is None:
        return None
    almacen = session.get(Almacen, almacen_id)
    return None if almacen is None or almacen.deleted_at is not None else almacen


def _abastecedor_valido(
    session: Session,
    almacen_solicitante_id: uuid.UUID,
    almacen_abastecedor_id: uuid.UUID | None,
) -> uuid.UUID:
    """De qué almacén se abastece este, con las cuatro cosas que tienen que
    ser ciertas para que el pedido signifique algo.

    Sin abastecedor explícito manda el principal del almacén, y **si el
    principal está dado de baja se cae al de respaldo** (RN-INV-022). Ese es
    el caso que el respaldo existe para cubrir: hasta ahora, dar de baja el
    central dejaba a la sucursal sin poder pedir nada y con un "almacén
    abastecedor no encontrado" que no le decía a nadie qué hacer.

    El explícito **no** cae al respaldo: quien nombra un almacén está pidiendo
    a ese, y darle otro en silencio sería despachar desde donde no se pidió.
    """
    solicitante = session.get(Almacen, almacen_solicitante_id)
    if solicitante is None or solicitante.deleted_at is not None:
        raise NoEncontrado("almacén solicitante no encontrado")

    abastecedor_id = almacen_abastecedor_id
    if abastecedor_id is None:
        principal = _vigente(session, solicitante.almacen_abastecedor_id)
        respaldo = _vigente(session, solicitante.almacen_abastecedor_respaldo_id)
        elegido = principal or respaldo
        abastecedor_id = elegido.id if elegido is not None else None
    if abastecedor_id is None:
        raise ReglaNegocio(
            "el almacén no tiene abastecedor vigente: indicar "
            "`almacen_abastecedor_id` o configurarlo en el almacén"
        )
    if abastecedor_id == almacen_solicitante_id:
        raise ReglaNegocio("un almacén no se abastece a sí mismo")
    abastecedor = _vigente(session, abastecedor_id)
    if abastecedor is None:
        raise NoEncontrado("almacén abastecedor no encontrado")
    if abastecedor.empresa_id != solicitante.empresa_id:
        raise ReglaNegocio("los dos almacenes deben ser de la misma empresa")
    return abastecedor_id


def _bajo_minimo(
    session: Session, almacen_id: uuid.UUID, sku_id: uuid.UUID
) -> bool:
    """Si el SKU está bajo su mínimo en ese almacén **ahora** (RN-INV-024).

    Sin fila de stock no hay mínimo declarado, y sin mínimo no hay urgencia
    que declarar: el ítem queda como pedido del local, que es lo que es.
    """
    fila = StockRepo(session).get(almacen_id, sku_id)
    return fila is not None and rules.stock_bajo(fila.cantidad, fila.stock_minimo)


def sugerir_items(
    session: Session, almacen_id: uuid.UUID
) -> list[tuple[uuid.UUID, Decimal]]:
    """Qué pedir y cuánto, según lo que el almacén tiene bajo su mínimo.

    Es la lista que el personal encuentra ya armada al abrir la pantalla
    (RN-INV-023). Sale del `stock_minimo` que el negocio ya declaró por
    almacén y SKU: no hay un segundo lugar donde configurar esto.
    """
    return [
        (fila.sku_id, rules.cantidad_a_reponer(fila.cantidad, fila.stock_minimo))
        for fila in StockRepo(session).list(almacen_id)
        if rules.stock_bajo(fila.cantidad, fila.stock_minimo)
    ]


def borrador_del_almacen(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    usuario_id: uuid.UUID,
) -> SolicitudInsumos:
    """La lista de la jornada de ese almacén, creándola si no existe.

    **Una por almacén y no por usuario** (RN-INV-023): durante el turno pasan
    varias personas por la misma cocina, y dos listas paralelas del mismo
    almacén son justo el problema que esto viene a resolver — el central
    recibiría dos pedidos que se solapan y ninguno completo.

    Al crearla se precarga con lo que está bajo mínimo; al volver a abrirla se
    suman los que cayeron desde entonces, sin tocar lo ya tecleado.
    """
    repo = SolicitudRepo(session)
    borrador = repo.borrador_de(almacen_id)
    if borrador is not None:
        refrescar_sugerencias(session, borrador)
        return borrador
    borrador = repo.add(
        SolicitudInsumos(
            almacen_solicitante_id=almacen_id,
            almacen_abastecedor_id=_abastecedor_valido(session, almacen_id, None),
            estado="borrador",
            solicitado_por=usuario_id,
        )
    )
    for sku_id, cantidad in sugerir_items(session, almacen_id):
        repo.add_item(
            SolicitudItem(
                solicitud_id=borrador.id,
                sku_id=sku_id,
                cantidad_solicitada=cantidad,
                bajo_minimo_al_pedir=True,
            )
        )
    return borrador


def refrescar_sugerencias(
    session: Session, borrador: SolicitudInsumos
) -> list[SolicitudItem]:
    """Suma al borrador los SKU que cayeron bajo mínimo desde la última vez.

    **Aditivo y nada más**: no corrige cantidades ni saca ítems. Lo que el
    personal escribió es una decisión tomada, y una sugerencia que la pise
    convierte la pantalla en algo que hay que revisar dos veces. Un SKU que se
    repuso tampoco se saca: si alguien lo dejó en la lista, lo quiere.

    ponytail: corre al abrir la pantalla, no en el beat de Celery. Techo: si
    nadie la abre, nadie ve lo nuevo. Upgrade si hace falta: la tarea diaria
    que ya existe en `application/tasks.py`.
    """
    if borrador.estado != "borrador":
        raise ReglaNegocio(f"la solicitud ya está {borrador.estado}")
    repo = SolicitudRepo(session)
    presentes = {item.sku_id for item in repo.items(borrador.id)}
    sumados = []
    for sku_id, cantidad in sugerir_items(session, borrador.almacen_solicitante_id):
        if sku_id in presentes:
            continue
        sumados.append(
            repo.add_item(
                SolicitudItem(
                    solicitud_id=borrador.id,
                    sku_id=sku_id,
                    cantidad_solicitada=cantidad,
                    bajo_minimo_al_pedir=True,
                )
            )
        )
    return sumados


def _borrador_editable(session: Session, solicitud_id: uuid.UUID) -> SolicitudInsumos:
    solicitud = SolicitudRepo(session).get(solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    if solicitud.estado != "borrador":
        raise ReglaNegocio(
            f"una solicitud {solicitud.estado} ya no se edita: se aprueba, "
            "se rechaza o se cancela"
        )
    return solicitud


def agregar_item(
    session: Session,
    solicitud_id: uuid.UUID,
    *,
    sku_id: uuid.UUID,
    cantidad: Decimal,
) -> SolicitudItem:
    """Suma a mano un SKU al borrador.

    Acá entra lo que el personal pide **sin que el stock lo pida**: la
    promoción del fin de semana, el insumo de una carta nueva. Queda con
    `bajo_minimo_al_pedir` en falso y el almacén lo ve marcado así
    (RN-INV-024): sigue siendo un pedido legítimo, pero no es una urgencia, y
    el almacenero ordena su día sabiéndolo.
    """
    solicitud = _borrador_editable(session, solicitud_id)
    if cantidad <= 0:
        raise ReglaNegocio("la cantidad solicitada debe ser positiva")
    if SkuRepo(session).get(sku_id) is None:
        raise NoEncontrado("SKU no encontrado")
    repo = SolicitudRepo(session)
    if repo.item(solicitud_id, sku_id) is not None:
        raise ReglaNegocio("el SKU ya está en la lista: cambiar su cantidad")
    return repo.add_item(
        SolicitudItem(
            solicitud_id=solicitud.id,
            sku_id=sku_id,
            cantidad_solicitada=cantidad,
            bajo_minimo_al_pedir=_bajo_minimo(
                session, solicitud.almacen_solicitante_id, sku_id
            ),
        )
    )


def cambiar_cantidad(
    session: Session,
    solicitud_id: uuid.UUID,
    *,
    sku_id: uuid.UUID,
    cantidad: Decimal,
) -> SolicitudItem:
    """Corrige lo sugerido. La marca de urgencia no se recalcula: dice qué vio
    el local al agregarlo, no cuánto terminó pidiendo."""
    _borrador_editable(session, solicitud_id)
    if cantidad <= 0:
        raise ReglaNegocio("la cantidad solicitada debe ser positiva")
    item = SolicitudRepo(session).item(solicitud_id, sku_id)
    if item is None:
        raise NoEncontrado("el SKU no está en la lista")
    item.cantidad_solicitada = cantidad
    return item


def quitar_item(
    session: Session, solicitud_id: uuid.UUID, *, sku_id: uuid.UUID
) -> None:
    """Saca un ítem del borrador — incluido uno sugerido: el almacén puede
    tener el insumo en camino y no necesita pedirlo otra vez."""
    _borrador_editable(session, solicitud_id)
    repo = SolicitudRepo(session)
    item = repo.item(solicitud_id, sku_id)
    if item is None:
        raise NoEncontrado("el SKU no está en la lista")
    repo.delete_item(item)


def enviar_borrador(
    session: Session, solicitud_id: uuid.UUID, enviado_por: uuid.UUID
) -> SolicitudInsumos:
    """Convierte la lista de la jornada en una solicitud que espera aprobación.

    El abastecedor se **vuelve a resolver** acá: entre que se abrió la lista y
    se envió pueden haber pasado horas, y si el central se dio de baja en el
    medio manda el respaldo (RN-INV-022). `solicitado_por` pasa a ser quien
    envía, que es quien responde por el pedido ante el aprobador.
    """
    solicitud = _borrador_editable(session, solicitud_id)
    if not SolicitudRepo(session).items(solicitud_id):
        raise ReglaNegocio("la solicitud necesita al menos un ítem")
    solicitud.almacen_abastecedor_id = _abastecedor_valido(
        session, solicitud.almacen_solicitante_id, None
    )
    solicitud.estado = "pendiente"
    solicitud.solicitado_por = enviado_por
    return solicitud


def crear_solicitud(
    session: Session,
    *,
    almacen_solicitante_id: uuid.UUID,
    items: list[tuple[uuid.UUID, Decimal]],
    solicitado_por: uuid.UUID,
    almacen_abastecedor_id: uuid.UUID | None = None,
    observacion: str | None = None,
    id: uuid.UUID | None = None,
    urgencias: dict[uuid.UUID, bool] | None = None,
) -> SolicitudInsumos:
    """Sin abastecedor explícito se usa el configurado en el almacén.

    `id` explícito lo usa el hub que ya creó la solicitud sin conexión
    (ADR-009): al reproducirla en la nube conserva su identidad, así que
    reenviar el mismo lote no la duplica y el local sigue viendo el mismo
    número que anotó en el papel.

    `urgencias` viaja por el mismo camino y por el mismo motivo: la marca de
    RN-INV-024 dice qué vio **el local** al pedir, y recalcularla contra el
    stock de la nube al reproducir el lote la volvería otra cosa. Sin ella
    —el caso normal, un pedido hecho en línea— se calcula acá.
    """
    if not items:
        raise ReglaNegocio("la solicitud necesita al menos un ítem")
    abastecedor_id = _abastecedor_valido(
        session, almacen_solicitante_id, almacen_abastecedor_id
    )
    repo = SolicitudRepo(session)
    if id is not None and repo.get(id) is not None:
        # Reproducción idempotente: el hub reenvía el lote entero cuando un
        # ítem falla, así que la solicitud que ya entró no se crea dos veces.
        return repo.get(id)
    solicitud = repo.add(
        SolicitudInsumos(
            id=id or uuid.uuid4(),
            almacen_solicitante_id=almacen_solicitante_id,
            almacen_abastecedor_id=abastecedor_id,
            estado="pendiente",
            solicitado_por=solicitado_por,
            observacion=observacion,
        )
    )
    vistos = set()
    for sku_id, cantidad in items:
        if cantidad <= 0:
            raise ReglaNegocio("la cantidad solicitada debe ser positiva")
        if sku_id in vistos:
            raise ReglaNegocio("el mismo SKU aparece dos veces en la solicitud")
        vistos.add(sku_id)
        repo.add_item(
            SolicitudItem(
                solicitud_id=solicitud.id,
                sku_id=sku_id,
                cantidad_solicitada=cantidad,
                bajo_minimo_al_pedir=(
                    urgencias[sku_id]
                    if urgencias is not None and sku_id in urgencias
                    else _bajo_minimo(session, almacen_solicitante_id, sku_id)
                ),
            )
        )
    return solicitud


def aprobar_solicitud(
    session: Session,
    solicitud_id: uuid.UUID,
    aprobado_por: uuid.UUID,
    aprobadas: dict[uuid.UUID, Decimal] | None = None,
) -> SolicitudInsumos:
    """Aprueba y reserva en el abastecedor.

    `aprobadas` permite recortar por SKU (lo pedido no siempre es lo que
    corresponde); lo que no se menciona se aprueba tal cual se pidió. Una
    cantidad aprobada en 0 deja el ítem fuera sin reservar nada.

    El aprobador no puede ser el solicitante: mismo criterio que el ajuste
    de inventario (RN-INV-006).
    """
    repo = SolicitudRepo(session)
    solicitud = repo.get(solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    if solicitud.estado != "pendiente":
        raise ReglaNegocio(f"la solicitud ya está {solicitud.estado}")
    if not rules.puede_aprobar(solicitud.solicitado_por, aprobado_por):
        raise ReglaNegocio("el aprobador no puede ser quien solicitó")

    aprobadas = aprobadas or {}
    for item in repo.items(solicitud_id):
        cantidad = aprobadas.get(item.sku_id, item.cantidad_solicitada)
        if cantidad < 0:
            raise ReglaNegocio("la cantidad aprobada no puede ser negativa")
        if cantidad > item.cantidad_solicitada:
            raise ReglaNegocio(
                "no se aprueba más de lo solicitado: pedido "
                f"{item.cantidad_solicitada}, aprobado {cantidad}"
            )
        item.cantidad_aprobada = cantidad
        if cantidad > 0:
            # Falla entera si un SKU no alcanza: aprobar a medias dejaría
            # reservas sueltas de una solicitud que nadie aprobó del todo.
            reservas_uc.reservar(
                session,
                almacen_id=solicitud.almacen_abastecedor_id,
                sku_id=item.sku_id,
                cantidad=cantidad,
                tipo="solicitud",
                creado_por=aprobado_por,
                referencia_id=solicitud.id,
            )
    solicitud.estado = "aprobada"
    solicitud.aprobado_por = aprobado_por
    return solicitud


def rechazar_solicitud(
    session: Session, solicitud_id: uuid.UUID, aprobado_por: uuid.UUID
) -> SolicitudInsumos:
    solicitud = SolicitudRepo(session).get(solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    if solicitud.estado != "pendiente":
        raise ReglaNegocio(f"la solicitud ya está {solicitud.estado}")
    solicitud.estado = "rechazada"
    solicitud.aprobado_por = aprobado_por
    return solicitud


def cancelar_solicitud(
    session: Session, solicitud_id: uuid.UUID, cancelado_por: uuid.UUID
) -> SolicitudInsumos:
    """Cancelar libera las reservas (RN-INV-010). Ya despachada no se
    cancela: eso movió stock y se corrige recibiendo o devolviendo."""
    solicitud = SolicitudRepo(session).get(solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    if solicitud.estado not in rules.ESTADOS_SOLICITUD_CANCELABLES:
        raise ReglaNegocio(
            f"una solicitud {solicitud.estado} ya no se cancela"
        )
    reservas_uc.liberar_por_referencia(session, solicitud.id, cancelado_por)
    solicitud.estado = "cancelada"
    return solicitud


def detalle(
    session: Session, solicitud_id: uuid.UUID
) -> tuple[SolicitudInsumos, list[SolicitudItem]]:
    repo = SolicitudRepo(session)
    solicitud = repo.get(solicitud_id)
    if solicitud is None:
        raise NoEncontrado("solicitud no encontrada")
    return solicitud, repo.items(solicitud_id)


def listar(
    session: Session,
    *,
    almacen_solicitante_id: uuid.UUID | None = None,
    estado: str | None = None,
    empresa_id: uuid.UUID | None = None,
) -> list[SolicitudInsumos]:
    return SolicitudRepo(session).list(almacen_solicitante_id, estado, empresa_id)


def q_listar(
    session: Session,
    *,
    almacen_solicitante_id: uuid.UUID | None = None,
    estado: str | None = None,
    empresa_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    marca_id: uuid.UUID | None = None,
    almacen_abastecedor_id: uuid.UUID | None = None,
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026).

    `sucursal_id` y `marca_id` se resuelven por el almacén solicitante: la
    solicitud vive por almacén y las dos preguntas están arriba de él. Los
    borradores quedan fuera salvo que se pida ese estado explícitamente.

    `almacen_abastecedor_id` responde la pregunta contraria —"qué me piden"—,
    que es la cola de trabajo del que despacha.
    """
    return SolicitudRepo(session).q_list(
        almacen_solicitante_id,
        estado,
        empresa_id,
        sucursal_id=sucursal_id,
        marca_id=marca_id,
        almacen_abastecedor_id=almacen_abastecedor_id,
    )
