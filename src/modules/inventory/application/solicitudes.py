"""Casos de uso de solicitud de insumos: el local pide, el supervisor
aprueba (RN-INV-001, RN-INV-010, RN-DOC-005).

Ciclo: `pendiente` → `aprobada` | `rechazada` | `cancelada` →
(el despacho la lleva a) `despachada` → `recibida`.

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
from src.modules.inventory.infrastructure.repositories import SolicitudRepo
from src.modules.users.infrastructure.models import Almacen


def _abastecedor_valido(
    session: Session,
    almacen_solicitante_id: uuid.UUID,
    almacen_abastecedor_id: uuid.UUID | None,
) -> uuid.UUID:
    """De qué almacén se abastece este, con las cuatro cosas que tienen que
    ser ciertas para que el pedido signifique algo."""
    solicitante = session.get(Almacen, almacen_solicitante_id)
    if solicitante is None or solicitante.deleted_at is not None:
        raise NoEncontrado("almacén solicitante no encontrado")

    abastecedor_id = almacen_abastecedor_id or solicitante.almacen_abastecedor_id
    if abastecedor_id is None:
        raise ReglaNegocio(
            "el almacén no tiene abastecedor configurado: indicar "
            "`almacen_abastecedor_id` o configurarlo en el almacén"
        )
    if abastecedor_id == almacen_solicitante_id:
        raise ReglaNegocio("un almacén no se abastece a sí mismo")
    abastecedor = session.get(Almacen, abastecedor_id)
    if abastecedor is None or abastecedor.deleted_at is not None:
        raise NoEncontrado("almacén abastecedor no encontrado")
    if abastecedor.empresa_id != solicitante.empresa_id:
        raise ReglaNegocio("los dos almacenes deben ser de la misma empresa")
    return abastecedor_id


def crear_solicitud(
    session: Session,
    *,
    almacen_solicitante_id: uuid.UUID,
    items: list[tuple[uuid.UUID, Decimal]],
    solicitado_por: uuid.UUID,
    almacen_abastecedor_id: uuid.UUID | None = None,
    observacion: str | None = None,
    id: uuid.UUID | None = None,
) -> SolicitudInsumos:
    """Sin abastecedor explícito se usa el configurado en el almacén.

    `id` explícito lo usa el hub que ya creó la solicitud sin conexión
    (ADR-009): al reproducirla en la nube conserva su identidad, así que
    reenviar el mismo lote no la duplica y el local sigue viendo el mismo
    número que anotó en el papel.
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
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return SolicitudRepo(session).q_list(almacen_solicitante_id, estado, empresa_id)
