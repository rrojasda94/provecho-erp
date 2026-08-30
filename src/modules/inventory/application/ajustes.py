"""Casos de uso de ajuste de inventario con segregación de funciones.

Solicitar y aprobar son acciones/permisos distintos y nunca del mismo
usuario. Al aprobarse se genera el movimiento y se refleja en el stock.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application import margenes
from src.modules.inventory.application import stock as stock_uc
from src.modules.inventory.application.errors import NoEncontrado, ReglaNegocio
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import Ajuste, Articulo, Sku
from src.modules.inventory.infrastructure.repositories import AjusteRepo, StockRepo
from src.modules.users.infrastructure.models import Almacen, Usuario
from src.shared import auditoria


def q_ajustes(
    session: Session,
    empresa_id: uuid.UUID | None = None,
    *,
    almacen_id: uuid.UUID | None = None,
    estado: str | None = None,
):
    """Consulta paginable de ajustes. `Ajuste` no lleva empresa: la hereda
    del almacén, igual que `stock` y `reserva` (ADR-004)."""
    q = select(Ajuste)
    if almacen_id is not None:
        q = q.where(Ajuste.almacen_id == almacen_id)
    if estado is not None:
        q = q.where(Ajuste.estado == estado)
    if empresa_id is not None:
        q = q.join(Almacen, Almacen.id == Ajuste.almacen_id).where(
            Almacen.empresa_id == empresa_id
        )
    # Los pendientes primero: la pantalla existe para aprobarlos o
    # rechazarlos, no para leer el histórico.
    return q.order_by(Ajuste.created_at.desc())


def detalle_ajuste(session: Session, ajuste_id: uuid.UUID) -> dict:
    """El ajuste con los nombres ya resueltos.

    A donde lleva `inventory.ajuste_fuera_margen`, y ahí se aprueba o se
    rechaza: la pantalla no puede pedir cuatro endpoints más para saber qué
    artículo es y quién lo pidió.
    """
    ajuste = AjusteRepo(session).get(ajuste_id)
    if ajuste is None:
        raise NoEncontrado("ajuste no encontrado")
    sku = session.get(Sku, ajuste.sku_id)
    articulo = session.get(Articulo, sku.articulo_id) if sku else None
    almacen = session.get(Almacen, ajuste.almacen_id)
    nombres = dict(
        session.execute(
            select(Usuario.id, Usuario.username).where(
                Usuario.id.in_(
                    {ajuste.solicitado_por, ajuste.aprobado_por} - {None}
                )
            )
        ).all()
    )
    return {
        "id": ajuste.id,
        "almacen_id": ajuste.almacen_id,
        "sku_id": ajuste.sku_id,
        "cantidad": ajuste.cantidad,
        "motivo": ajuste.motivo,
        "estado": ajuste.estado,
        "conteo_id": ajuste.conteo_id,
        "solicitado_por": ajuste.solicitado_por,
        "aprobado_por": ajuste.aprobado_por,
        "dentro_margen": ajuste.dentro_margen,
        "lote_id": ajuste.lote_id,
        "articulo": articulo.nombre if articulo else "(borrado)",
        "sku_codigo": sku.codigo if sku else "(borrado)",
        "almacen": almacen.nombre if almacen else "(borrado)",
        "solicitante": nombres.get(ajuste.solicitado_por, "(borrado)"),
        "aprobador": (
            nombres.get(ajuste.aprobado_por, "(borrado)")
            if ajuste.aprobado_por
            else None
        ),
    }


def solicitar_ajuste(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    motivo: str,
    solicitado_por: uuid.UUID,
    lote_codigo: str | None = None,
    fecha_vencimiento: date | None = None,
    fecha_elaboracion: date | None = None,
    condicion_almacenamiento: str | None = None,
) -> Ajuste:
    if motivo not in rules.MOTIVOS_AJUSTE:
        raise ReglaNegocio(f"motivo de ajuste inválido: {motivo}")
    if not rules.signo_ajuste_valido(motivo, cantidad):
        raise ReglaNegocio(
            f"signo de cantidad ({cantidad}) inválido para motivo '{motivo}'"
        )
    datos_de_lote = any(
        (lote_codigo, fecha_vencimiento, fecha_elaboracion, condicion_almacenamiento)
    )
    if datos_de_lote and cantidad <= 0:
        raise ReglaNegocio(
            "los datos de lote solo aplican a una entrada (cantidad positiva); "
            "una salida de un artículo con control de lote reparte por FEFO"
        )
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        raise NoEncontrado("almacén no encontrado")
    margen, piso = margenes.margen_de_empresa(session, almacen.empresa_id)
    fila = StockRepo(session).get(almacen_id, sku_id)
    costo = margenes.costos_por_sku(session, [sku_id]).get(sku_id, Decimal(0))
    dentro_margen = rules.diferencia_dentro_margen(
        fila.cantidad if fila else Decimal(0),
        cantidad,
        margen,
        valor_diferencia=cantidad * costo,
        piso=piso,
    )
    lote_id = None
    if cantidad > 0 and datos_de_lote:
        articulo = lotes_uc.articulo_de_sku(session, sku_id)
        if articulo.controla_lote:
            lote_id = lotes_uc.crear_lote(
                session,
                articulo_id=articulo.id,
                codigo=lote_codigo,
                fecha_vencimiento=fecha_vencimiento,
                fecha_elaboracion=fecha_elaboracion,
                origen="carga_inicial",
                referencia=str(almacen_id),
                condicion_almacenamiento=condicion_almacenamiento,
            ).id
    return AjusteRepo(session).add(
        Ajuste(
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=cantidad,
            motivo=motivo,
            solicitado_por=solicitado_por,
            dentro_margen=dentro_margen,
            estado="pendiente",
            lote_id=lote_id,
        )
    )


def aprobar_ajuste(
    session: Session, ajuste_id: uuid.UUID, aprobado_por: uuid.UUID
) -> Ajuste:
    ajuste = AjusteRepo(session).get(ajuste_id)
    if ajuste is None:
        raise NoEncontrado("ajuste no encontrado")
    if ajuste.estado != "pendiente":
        raise ReglaNegocio(f"el ajuste ya está {ajuste.estado}")
    if not rules.puede_aprobar(ajuste.solicitado_por, aprobado_por):
        raise ReglaNegocio("el aprobador no puede ser el solicitante del ajuste")

    comun = {
        "almacen_id": ajuste.almacen_id,
        "sku_id": ajuste.sku_id,
        "tipo": "ajuste",
        "usuario_id": aprobado_por,
        "referencia": str(ajuste.id),
        "motivo_ajuste": ajuste.motivo,
        # Solo lo pobló `solicitar_ajuste` en la rama de entrada (cantidad
        # positiva); `registrar_movimiento` ignora `lote_id=None` y crea el
        # lote automático de siempre. `registrar_salida` (rama negativa) no
        # lo lee — reparte por FEFO.
        "lote_id": ajuste.lote_id,
    }
    if ajuste.cantidad < 0:
        # Un ajuste negativo de un artículo con lote puede repartirse entre
        # varios lotes (FEFO): `movimiento_id` guarda el primero y todos
        # comparten `referencia`, así la traza completa sigue siendo una
        # consulta por referencia.
        movs = stock_uc.registrar_salida(session, cantidad=-ajuste.cantidad, **comun)
    else:
        mov, _ = stock_uc.registrar_movimiento(
            session, cantidad=ajuste.cantidad, **comun
        )
        movs = [mov]
    ajuste.aprobado_por = aprobado_por
    ajuste.estado = "aprobado"
    ajuste.movimiento_id = movs[0].id

    almacen = session.get(Almacen, ajuste.almacen_id)
    auditoria.registrar(
        session,
        usuario_id=aprobado_por,
        entidad="ajuste",
        entidad_id=ajuste.id,
        accion="aprobar",
        datos_antes={"estado": "pendiente"},
        datos_despues={
            "estado": "aprobado",
            "cantidad": str(ajuste.cantidad),
            "sku_id": str(ajuste.sku_id),
            "motivo": ajuste.motivo,
            "dentro_margen": ajuste.dentro_margen,
        },
        empresa_id=almacen.empresa_id if almacen else None,
        sucursal_id=almacen.sucursal_id if almacen else None,
    )

    if not ajuste.dentro_margen:
        event_bus.publish(
            "inventory.ajuste_fuera_margen",
            {
                "ajuste_id": str(ajuste.id),
                "almacen_id": str(ajuste.almacen_id),
                # Quien lo aprobó, no quien lo solicitó: el hecho reportado es
                # que un ajuste fuera de margen se ejecutó.
                "aprobado_por": str(aprobado_por),
                "sku_id": str(ajuste.sku_id),
                "cantidad": str(ajuste.cantidad),
                "motivo": ajuste.motivo,
            },
            session=session,
        )
    return ajuste


def rechazar_ajuste(
    session: Session, ajuste_id: uuid.UUID, aprobado_por: uuid.UUID
) -> Ajuste:
    ajuste = AjusteRepo(session).get(ajuste_id)
    if ajuste is None:
        raise NoEncontrado("ajuste no encontrado")
    if ajuste.estado != "pendiente":
        raise ReglaNegocio(f"el ajuste ya está {ajuste.estado}")
    ajuste.aprobado_por = aprobado_por
    ajuste.estado = "rechazado"
    return ajuste
