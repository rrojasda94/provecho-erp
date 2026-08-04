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

from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    Cliente,
    MedioPago,
    Pago,
    ProductoComercial,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.infrastructure.models import Persona, Sucursal
from src.shared import fechas


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
    fecha = fecha or fechas.hoy()
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


def puntos_venta_de_empresa(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[uuid.UUID]:
    """IDs de `punto_venta` de la empresa — `accounting` no importa
    `PuntoVenta` directo (es dominio de `sales`, no organización
    transversal), lo resuelve por acá para escopar caja por empresa.

    `empresa_id=None` = sin filtro: solo lo usa un superusuario sin empresa
    asignada (`Tenant.filtro_empresa`)."""
    stmt = select(PuntoVenta.id).join(Sucursal, Sucursal.id == PuntoVenta.sucursal_id)
    if empresa_id is not None:
        stmt = stmt.where(Sucursal.empresa_id == empresa_id)
    return list(session.scalars(stmt))


def sucursal_de_punto_venta(
    session: Session, punto_venta_id: uuid.UUID
) -> uuid.UUID | None:
    """Sucursal a la que pertenece un punto de venta — `accounting` la
    necesita para validar el alcance de tenant de caja/arqueo (ADR-004) sin
    importar `PuntoVenta`, que es dominio de `sales`."""
    return session.scalar(
        select(PuntoVenta.sucursal_id).where(PuntoVenta.id == punto_venta_id)
    )


def venta_para_encuesta(session: Session, venta_id: uuid.UUID) -> dict | None:
    """Lo mínimo que `marketing` necesita para decidir la encuesta de
    satisfacción (RN-COM-007): sucursal (para el alcance de tenant), cliente
    y si el pedido ya se entregó. `marketing` no importa `Venta`/`VentaItem`.

    `None` = la venta no existe."""
    venta = session.get(Venta, venta_id)
    if venta is None:
        return None
    estados = list(
        session.scalars(
            select(VentaItem.estado_preparacion).where(VentaItem.venta_id == venta_id)
        )
    )
    return {
        "id": venta.id,
        "sucursal_id": venta.sucursal_id,
        "cliente_id": venta.cliente_id,
        "entregada": rules.pedido_entregado(estados),
    }


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


def productos_que_usan_receta(session: Session, receta_id: uuid.UUID) -> list[str]:
    """Nombres de los productos comerciales que apuntan a esta receta.

    Lo consulta `inventory` antes de borrarla: la FK lo impediría igual, pero
    en la base y con un error de integridad ilegible. Acá el mensaje puede
    decir **cuál** producto la está usando, que es lo que el usuario necesita
    para desatascarse.
    """
    return list(
        session.scalars(
            select(ProductoComercial.nombre)
            .where(ProductoComercial.receta_id == receta_id)
            .order_by(ProductoComercial.nombre)
        )
    )
