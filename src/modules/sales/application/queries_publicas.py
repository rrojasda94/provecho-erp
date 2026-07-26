"""Contrato público de lectura de `sales` para otros módulos.

Único punto de entrada para que otro módulo (hoy: análisis vía API,
`accounting` para reconciliar cierre de caja, dashboard vía `core`; a
futuro: `marketing` cuando exista como módulo) lea datos de `sales`. Nunca
importar `sales.domain`/`sales.infrastructure` directamente desde otro
módulo — solo las funciones de este archivo, que devuelven DTOs (dicts),
nunca el ORM.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.sales.infrastructure.models import Cliente, MedioPago, Pago, PuntoVenta, Venta
from src.modules.users.infrastructure.models import Persona, Sucursal


def listar_clientes_para_analisis(
    session: Session,
    grupo_id: uuid.UUID,
    *,
    tipo: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = (
        select(Cliente, Persona)
        .outerjoin(Persona, Persona.id == Cliente.persona_id)
        .where(Cliente.grupo_id == grupo_id, Cliente.deleted_at.is_(None))
        .limit(limit)
    )
    if tipo is not None:
        stmt = stmt.where(Cliente.tipo == tipo)

    resultado = []
    for cliente, persona in session.execute(stmt):
        nombre = (
            f"{persona.nombres} {persona.apellidos}"
            if persona is not None
            else cliente.razon_social
        )
        resultado.append(
            {
                "id": cliente.id,
                "tipo": cliente.tipo,
                "nombre": nombre,
                "contacto": cliente.contacto,
            }
        )
    return resultado


# Ventas que ya representan ingreso real — una orden sin pagar o anulada
# no cuenta para el resumen del día ni para reconciliar caja.
_ESTADOS_CON_INGRESO = ("pagada", "facturada")


def resumen_ventas_del_dia(
    session: Session, empresa_id: uuid.UUID, *, fecha: date | None = None
) -> dict:
    """Cantidad y total de ventas cobradas hoy, para el dashboard gerencial.

    Filtra por `fecha_orden` (día de negocio) y `empresa_id`, vía
    `sucursal.empresa_id` — `venta` no repite el tenant directo.
    """
    fecha = fecha or date.today()
    fila = session.execute(
        select(func.count(Venta.id), func.coalesce(func.sum(Venta.total), 0))
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .where(
            Sucursal.empresa_id == empresa_id,
            Venta.fecha_orden == fecha,
            Venta.estado.in_(_ESTADOS_CON_INGRESO),
        )
    ).one()
    cantidad, total = fila
    return {"fecha": fecha, "cantidad": cantidad, "total": Decimal(total)}


def puntos_venta_de_empresa(session: Session, empresa_id: uuid.UUID) -> list[uuid.UUID]:
    """IDs de `punto_venta` de la empresa — `accounting` no importa
    `PuntoVenta` directo (es dominio de `sales`, no organización
    transversal), lo resuelve por acá para escopar caja por empresa."""
    return list(
        session.scalars(
            select(PuntoVenta.id)
            .join(Sucursal, Sucursal.id == PuntoVenta.sucursal_id)
            .where(Sucursal.empresa_id == empresa_id)
        )
    )


def total_efectivo_cobrado(
    session: Session, punto_venta_id: uuid.UUID, desde: datetime
) -> Decimal:
    """Suma de pagos confirmados en efectivo de ventas de este punto de
    venta desde `desde` — usado por `accounting` para reconciliar el cierre
    de caja (PROC-CTB-001); nunca se llama al revés (accounting no expone
    su dominio a sales)."""
    total = session.scalar(
        select(func.coalesce(func.sum(Pago.monto), 0))
        .join(Venta, Venta.id == Pago.venta_id)
        .join(MedioPago, MedioPago.id == Pago.medio_pago_id)
        .where(
            Venta.punto_venta_id == punto_venta_id,
            Pago.estado == "confirmado",
            Pago.created_at >= desde,
            MedioPago.tipo == "efectivo",
        )
    )
    return Decimal(total)
