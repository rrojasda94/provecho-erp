"""Contrato público de lectura de `sales` para otros módulos.

Único punto de entrada para que otro módulo (hoy: análisis vía API,
`accounting` para reconciliar cierre de caja, dashboard vía `core`; a
futuro: `marketing` cuando exista como módulo) lea datos de `sales`. Nunca
importar `sales.domain`/`sales.infrastructure` directamente desde otro
módulo — solo las funciones de este archivo, que devuelven DTOs (dicts),
nunca el ORM.
"""

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    AlertaPedido,
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


def _ventas_en_rango(
    empresa_id: uuid.UUID | None,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None,
):
    """Predicados comunes de los reportes de venta: mismo criterio de
    "esto fue ingreso real" y mismo escopado por tenant en los tres, para
    que un ranking y una serie del mismo rango nunca se contradigan."""
    condiciones = [
        Venta.fecha_orden >= desde,
        Venta.fecha_orden <= hasta,
        Venta.estado.in_(_ESTADOS_CON_INGRESO),
    ]
    if empresa_id is not None:
        condiciones.append(Sucursal.empresa_id == empresa_id)
    if sucursal_ids:
        condiciones.append(Venta.sucursal_id.in_(list(sucursal_ids)))
    return condiciones


def ventas_por_dia(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
) -> list[dict]:
    """Serie diaria de ventas cobradas, para el reporte de tendencia.

    Agrupa por `fecha_orden` (día de negocio, ya resuelto en zona local al
    crear la venta) y no por `created_at`: agrupar el instante UTC partiría
    en dos la noche de un local que cierra pasada la medianoche."""
    filas = session.execute(
        select(
            Venta.fecha_orden,
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
        )
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .where(*_ventas_en_rango(empresa_id, desde, hasta, sucursal_ids))
        .group_by(Venta.fecha_orden)
        .order_by(Venta.fecha_orden)
    )
    return [
        {"fecha": fecha, "cantidad": cantidad, "total": Decimal(total)}
        for fecha, cantidad, total in filas
    ]


def ventas_por_sucursal(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
) -> list[dict]:
    """Ranking de sucursales por venta cobrada en el rango."""
    filas = session.execute(
        select(
            Venta.sucursal_id,
            Sucursal.nombre,
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
        )
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .where(*_ventas_en_rango(empresa_id, desde, hasta, sucursal_ids))
        .group_by(Venta.sucursal_id, Sucursal.nombre)
        .order_by(func.coalesce(func.sum(Venta.total), 0).desc())
    )
    return [
        {
            "sucursal_id": sucursal_id,
            "sucursal": nombre,
            "cantidad": cantidad,
            "total": Decimal(total),
        }
        for sucursal_id, nombre, cantidad, total in filas
    ]


def top_productos(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
    limite: int = 20,
) -> list[dict]:
    """Productos más vendidos del rango, por unidades e importe.

    El importe se recalcula desde el ítem (`cantidad * precio - descuento`)
    en vez de repartir `venta.total`: el total de la venta ya trae descuentos
    de orden y no se puede atribuir a un producto sin inventar un criterio.
    """
    importe = VentaItem.cantidad * VentaItem.precio_unitario - VentaItem.descuento
    filas = session.execute(
        select(
            ProductoComercial.nombre,
            func.sum(VentaItem.cantidad),
            func.coalesce(func.sum(importe), 0),
        )
        .select_from(VentaItem)
        .join(Venta, Venta.id == VentaItem.venta_id)
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .join(
            ProductoComercial,
            ProductoComercial.id == VentaItem.producto_comercial_id,
        )
        .where(*_ventas_en_rango(empresa_id, desde, hasta, sucursal_ids))
        .group_by(ProductoComercial.nombre)
        .order_by(func.sum(VentaItem.cantidad).desc())
        .limit(limite)
    )
    return [
        {"producto": nombre, "cantidad": Decimal(cantidad), "total": Decimal(total)}
        for nombre, cantidad, total in filas
    ]


def ventas_por_hora(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
) -> list[dict]:
    """Cuánto se vende en cada hora del día — base para dimensionar turnos.

    La base agrupa por hora **UTC** (`extract` es lo único portable entre
    SQLite y Postgres) y acá se corre la etiqueta al huso del negocio. Son
    24 filas: reetiquetarlas es exacto y no cuesta nada, mientras que
    convertir cada venta antes de agrupar obligaría a traerlas todas.
    """
    hora_utc = func.cast(func.extract("hour", Venta.created_at), Integer)
    filas = session.execute(
        select(
            hora_utc.label("hora"),
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
        )
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .where(*_ventas_en_rango(empresa_id, desde, hasta, sucursal_ids))
        .group_by(hora_utc)
    )
    desfase = fechas.desfase_horas()
    por_hora: dict[int, dict] = {}
    for hora, cantidad, total in filas:
        local = (int(hora) + desfase) % 24
        acumulado = por_hora.setdefault(
            local, {"cantidad": 0, "total": Decimal(0)}
        )
        acumulado["cantidad"] += cantidad
        acumulado["total"] += Decimal(total)
    return [
        {
            "hora": f"{h:02d}:00",
            "cantidad": por_hora[h]["cantidad"],
            "total": por_hora[h]["total"],
        }
        for h in sorted(por_hora)
    ]


def ventas_por_usuario(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
    limite: int = 20,
) -> list[dict]:
    """Ranking de quién atendió más venta, por `venta.usuario_id`.

    Devuelve el id, no el nombre: `sales` no conoce a `trabajador` (es
    dominio de `rrhh`). Quien componga el reporte resuelve el nombre por el
    contrato público de `rrhh`.
    """
    filas = session.execute(
        select(
            Venta.usuario_id,
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
        )
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .where(*_ventas_en_rango(empresa_id, desde, hasta, sucursal_ids))
        .group_by(Venta.usuario_id)
        .order_by(func.coalesce(func.sum(Venta.total), 0).desc())
        .limit(limite)
    )
    return [
        {"usuario_id": usuario_id, "cantidad": cantidad, "total": Decimal(total)}
        for usuario_id, cantidad, total in filas
    ]


def vendido_por_producto(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
    limite: int = 20,
) -> list[dict]:
    """Unidades e importe por producto, **con su `receta_id`** para que
    quien calcule margen pueda pedirle el costo a `inventory` sin que
    `sales` tenga que conocer recetas."""
    importe = VentaItem.cantidad * VentaItem.precio_unitario - VentaItem.descuento
    filas = session.execute(
        select(
            ProductoComercial.nombre,
            ProductoComercial.receta_id,
            func.sum(VentaItem.cantidad),
            func.coalesce(func.sum(importe), 0),
        )
        .select_from(VentaItem)
        .join(Venta, Venta.id == VentaItem.venta_id)
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .join(
            ProductoComercial,
            ProductoComercial.id == VentaItem.producto_comercial_id,
        )
        .where(*_ventas_en_rango(empresa_id, desde, hasta, sucursal_ids))
        .group_by(ProductoComercial.nombre, ProductoComercial.receta_id)
        .order_by(func.coalesce(func.sum(importe), 0).desc())
        .limit(limite)
    )
    return [
        {
            "producto": nombre,
            "receta_id": receta_id,
            "cantidad": Decimal(cantidad),
            "ingreso": Decimal(ingreso),
        }
        for nombre, receta_id, cantidad, ingreso in filas
    ]


def pedidos_demorados(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
    limite: int = 50,
) -> list[dict]:
    """Alertas de pedido que superó su tiempo en cocina, para el tablero.

    Se lee de `alerta_pedido` y no se recalcula en vivo: la alerta guarda el
    umbral vigente **en ese momento**, así que subir el parámetro mañana no
    reescribe lo que ayer se consideró demora.
    """
    stmt = (
        select(AlertaPedido, Sucursal.nombre, Venta.numero_orden, Venta.fecha_orden)
        .join(Sucursal, Sucursal.id == AlertaPedido.sucursal_id)
        .join(Venta, Venta.id == AlertaPedido.venta_id)
        .where(
            AlertaPedido.created_at >= fechas.inicio_dia_utc(desde),
            AlertaPedido.created_at <= fechas.fin_dia_utc(hasta),
        )
        .order_by(AlertaPedido.minutos_transcurridos.desc())
        .limit(limite)
    )
    if empresa_id is not None:
        stmt = stmt.where(Sucursal.empresa_id == empresa_id)
    if sucursal_ids:
        stmt = stmt.where(AlertaPedido.sucursal_id.in_(list(sucursal_ids)))

    return [
        {
            "pedido": f"#{numero}",
            "fecha": fecha_orden,
            "sucursal": sucursal,
            "minutos": alerta.minutos_transcurridos,
            "umbral": alerta.minutos_umbral,
            "estado": alerta.estado_al_alertar,
            "items_pendientes": alerta.items_pendientes,
            # Lo que separa "pasó y se resolvió" de "está pasando ahora".
            "atendida": "sí" if alerta.atendida_at is not None else "no",
        }
        for alerta, sucursal, numero, fecha_orden in session.execute(stmt)
    ]


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


def puntos_venta_de_sucursal(
    session: Session, sucursal_id: uuid.UUID
) -> list[uuid.UUID]:
    """IDs de `punto_venta` de una sucursal. Lo usa `accounting` para
    encontrar la caja abierta del local sin importar `PuntoVenta`."""
    return list(
        session.scalars(
            select(PuntoVenta.id).where(PuntoVenta.sucursal_id == sucursal_id)
        )
    )


def puntos_venta_rotulados(
    session: Session, punto_venta_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """`punto_venta_id` → un rótulo legible ("CH1 · B001").

    `punto_venta` no tiene nombre propio, así que se arma con la sucursal y
    la serie de boleta, que es como el negocio distingue una caja de otra.
    Lo necesita `accounting` para su reporte de caja: sin esto la tabla
    muestra horas y montos sin decir **de qué caja**, que es el primer dato
    que hace falta para ir a cerrarla.
    """
    if not punto_venta_ids:
        return {}
    filas = session.execute(
        select(PuntoVenta.id, Sucursal.nombre, PuntoVenta.serie_boleta)
        .join(Sucursal, Sucursal.id == PuntoVenta.sucursal_id)
        .where(PuntoVenta.id.in_(list(punto_venta_ids)))
    )
    return {pv_id: f"{sucursal} · {serie}" for pv_id, sucursal, serie in filas}


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


def contacto_de_cliente(session: Session, cliente_id: uuid.UUID) -> dict | None:
    """Nombre y teléfono del cliente, para mandarle algo (hoy: la encuesta de
    satisfacción de `marketing` por WhatsApp).

    El teléfono sale de `persona` si el cliente es natural y, si no, de
    `cliente.contacto` — que es el campo tecleado en caja y donde termina el
    número de un cliente jurídico. Devuelve `None` si el cliente no existe;
    `telefono` vacío si existe pero no hay a dónde escribirle, que es una
    respuesta distinta y el llamador la trata distinto.
    """
    fila = session.execute(
        select(Cliente, Persona)
        .outerjoin(Persona, Persona.id == Cliente.persona_id)
        .where(Cliente.id == cliente_id, Cliente.deleted_at.is_(None))
    ).first()
    if fila is None:
        return None
    cliente, persona = fila
    nombre = (
        f"{persona.nombres} {persona.apellidos}".strip()
        if persona is not None
        else (cliente.razon_social or "")
    )
    telefono = (persona.telefono if persona is not None else None) or cliente.contacto
    return {"id": cliente.id, "nombre": nombre, "telefono": telefono or ""}


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


def total_tarjeta_cobrado(
    session: Session, punto_venta_id: uuid.UUID, desde: datetime
) -> Decimal:
    """Lo cobrado con tarjeta en este punto de venta desde `desde`.

    El cierre de caja cuadra efectivo **y** tarjetas (RN-POS-004): sin este
    número, la mitad del turno se cierra a ojo y un cobro mal pasado en el
    POS solo aparece en la liquidación del operador, semanas después.

    Crédito y débito juntos: al arqueo le importa el total que el lote de
    los terminales tiene que respaldar, no con cuál de las dos se pagó.
    """
    total = session.scalar(
        select(func.coalesce(func.sum(Pago.monto), 0))
        .join(Venta, Venta.id == Pago.venta_id)
        .join(MedioPago, MedioPago.id == Pago.medio_pago_id)
        .where(
            Venta.punto_venta_id == punto_venta_id,
            Pago.estado == "confirmado",
            Pago.created_at >= desde,
            MedioPago.tipo.in_(("tarjeta_credito", "tarjeta_debito")),
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
