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

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.orm import Session

from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    AlertaPedido,
    Cliente,
    MedioPago,
    Mesa,
    Pago,
    ProductoAtributoLinea,
    ProductoAtributoValor,
    ProductoComercial,
    Promocion,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.infrastructure.models import Marca, Persona, Sucursal
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
        acumulado = por_hora.setdefault(local, {"cantidad": 0, "total": Decimal(0)})
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


def mesas_preferidas(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None = None,
    limite: int = 20,
) -> list[dict]:
    """Ranking de qué mesa pide más el cliente, por sucursal.

    Reusa `_ventas_en_rango`: mismo criterio de "esto fue ingreso real" que
    el resto de reportes de venta, para que este ranking no contradiga a
    los demás sobre el mismo rango. La etiqueta lleva la sucursal adentro
    porque el gráfico solo dibuja una columna y "Mesa 4" se repite entre
    locales — sin el local, dos barras se confundirían en una.
    """
    filas = session.execute(
        select(
            Sucursal.nombre,
            Mesa.numero,
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
        )
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .join(Mesa, Mesa.id == Venta.mesa_id)
        .where(
            Venta.mesa_id.is_not(None),
            *_ventas_en_rango(empresa_id, desde, hasta, sucursal_ids),
        )
        .group_by(Sucursal.nombre, Mesa.numero)
        .order_by(func.count(Venta.id).desc())
        .limit(limite)
    )
    return [
        {
            "mesa": f"{sucursal} · Mesa {numero}",
            "cantidad": cantidad,
            "total": Decimal(total),
        }
        for sucursal, numero, cantidad, total in filas
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
            # El id ancla el enlace de la fila (ADR-036): la demora se atiende
            # en la venta, no en el tablero.
            "venta_id": alerta.venta_id,
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


def puntos_venta_de_sucursal(session: Session, sucursal_id: uuid.UUID) -> list[uuid.UUID]:
    """IDs de `punto_venta` de una sucursal. Lo usa `accounting` para
    encontrar la caja abierta del local sin importar `PuntoVenta`."""
    return list(session.scalars(select(PuntoVenta.id).where(PuntoVenta.sucursal_id == sucursal_id)))


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


def sucursal_de_punto_venta(session: Session, punto_venta_id: uuid.UUID) -> uuid.UUID | None:
    """Sucursal a la que pertenece un punto de venta — `accounting` la
    necesita para validar el alcance de tenant de caja/arqueo (ADR-004) sin
    importar `PuntoVenta`, que es dominio de `sales`."""
    return session.scalar(select(PuntoVenta.sucursal_id).where(PuntoVenta.id == punto_venta_id))


def venta_para_encuesta(session: Session, venta_id: uuid.UUID) -> dict | None:
    """Lo mínimo que `marketing` necesita para decidir la encuesta de
    satisfacción (RN-COM-007): sucursal (para el alcance de tenant), cliente
    y si el pedido ya se entregó. `marketing` no importa `Venta`/`VentaItem`.

    `None` = la venta no existe."""
    venta = session.get(Venta, venta_id)
    if venta is None:
        return None
    estados = list(
        session.scalars(select(VentaItem.estado_preparacion).where(VentaItem.venta_id == venta_id))
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


def venta_para_reparto(session: Session, venta_id: uuid.UUID) -> dict | None:
    """Lo que `delivery` necesita para asignar y rutear una venta (ADR-098):
    sucursal, modalidad, canal, dirección/ubicación, la distancia ya
    cotizada, el total (para el "monto a cobrar" que ve el repartidor en
    una venta todavía `orden`, sin pagar), si tiene plataforma externa
    (RN-PER-003 la excluye del reparto propio) y si todos sus ítems
    llegaron a `listo` o ya se entregó. `delivery` no importa
    `Venta`/`VentaItem` — pasa siempre por acá.

    `None` = la venta no existe.
    """
    venta = session.get(Venta, venta_id)
    if venta is None:
        return None
    estados = list(
        session.scalars(select(VentaItem.estado_preparacion).where(VentaItem.venta_id == venta_id))
    )
    return {
        "id": venta.id,
        "sucursal_id": venta.sucursal_id,
        "numero_orden": venta.numero_orden,
        "fecha_orden": venta.fecha_orden,
        "modalidad": venta.modalidad,
        "canal": venta.canal,
        "estado": venta.estado,
        "cliente_id": venta.cliente_id,
        "direccion_entrega": venta.direccion_entrega,
        "ubicacion_lat": venta.ubicacion_lat,
        "ubicacion_lng": venta.ubicacion_lng,
        "distancia_entrega_km": venta.distancia_entrega_km,
        "repartidor_externo_plataforma": venta.repartidor_externo_plataforma,
        "total": venta.total,
        "lista": rules.pedido_entregable(estados),
        "entregada": rules.pedido_entregado(estados),
    }


def ventas_listas_para_reparto(
    session: Session,
    sucursal_ids: Sequence[uuid.UUID],
    *,
    fecha: date | None = None,
) -> list[dict]:
    """Ventas delivery listas para entrar a una ruta: modalidad delivery,
    sin plataforma externa (RN-PER-003), no anuladas, con todos los ítems
    en `listo` y ninguno todavía `entregado`.

    `delivery` resuelve así su tablero de "listos sin asignar" en vez de
    consumir `sales.pedido_listo` (ADR-098): una consulta activa encuentra
    igual a un pedido que llegó a `listo` antes de que existiera su ruta, o
    que cambió a delivery después de estar listo — un evento que ya pasó
    nunca lo habría avisado.
    """
    if not sucursal_ids:
        return []
    stmt = select(Venta).where(
        Venta.sucursal_id.in_(list(sucursal_ids)),
        Venta.modalidad == "delivery",
        Venta.repartidor_externo_plataforma.is_(None),
        Venta.estado != "anulada",
    )
    if fecha is not None:
        stmt = stmt.where(Venta.fecha_orden == fecha)
    ventas = list(session.scalars(stmt.order_by(Venta.created_at)))
    if not ventas:
        return []

    estados_por_venta: dict[uuid.UUID, list[str]] = {v.id: [] for v in ventas}
    filas = session.execute(
        select(VentaItem.venta_id, VentaItem.estado_preparacion).where(
            VentaItem.venta_id.in_(list(estados_por_venta))
        )
    )
    for venta_id, estado in filas:
        estados_por_venta[venta_id].append(estado)

    resultado = []
    for venta in ventas:
        estados = estados_por_venta[venta.id]
        if not rules.pedido_entregable(estados) or rules.pedido_entregado(estados):
            continue
        resultado.append(
            {
                "id": venta.id,
                "sucursal_id": venta.sucursal_id,
                "numero_orden": venta.numero_orden,
                "fecha_orden": venta.fecha_orden,
                "cliente_id": venta.cliente_id,
                "direccion_entrega": venta.direccion_entrega,
                "ubicacion_lat": venta.ubicacion_lat,
                "ubicacion_lng": venta.ubicacion_lng,
                "distancia_entrega_km": venta.distancia_entrega_km,
            }
        )
    return resultado


def total_efectivo_cobrado(session: Session, punto_venta_id: uuid.UUID, desde: datetime) -> Decimal:
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


def total_tarjeta_cobrado(session: Session, punto_venta_id: uuid.UUID, desde: datetime) -> Decimal:
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


def valores_ofrecidos_de_receta(session: Session, receta_id: uuid.UUID) -> set[str]:
    """`producto_atributo_valor.id` (texto) que algún producto de esta receta
    puede recibir — la unión de `catalogo.valores_ofrecidos` de cada uno.

    Lo consulta `inventory` para validar `receta_item.aplica_valores` al
    escribir: la condición de una línea nombra valores del producto que usa
    la receta, y sin este contrato el servidor no tenía cómo saber si un
    valor pertenece a algo que de verdad vende esa receta. Conjunto vacío =
    ningún producto la usa (o ninguno ofrece nada) — el llamador decide qué
    hacer con eso, acá no hay nada contra qué validar.
    """
    # Import diferido: `catalogo` importa `inventory.queries_publicas`, que
    # importa `recetas`, que importa este módulo — a nivel de archivo el
    # ciclo se cerraría.
    from src.modules.sales.application import catalogo as catalogo_uc

    productos = list(
        session.scalars(select(ProductoComercial).where(ProductoComercial.receta_id == receta_id))
    )
    ofrecidos: set[str] = set()
    for producto in productos:
        ofrecidos |= catalogo_uc.valores_ofrecidos(session, producto)
    return ofrecidos


def atributo_de_valores(session: Session, valor_ids: Sequence[uuid.UUID | str]) -> dict[str, str]:
    """`producto_atributo_valor.id` → `atributo.id`, los dos como texto.

    Lo consulta `inventory` para decidir si una línea de receta condicionada
    le toca a la combinación vendida: la regla agrupa los valores **por
    atributo** y exige uno de cada grupo (RN-COM-037), así que sin saber a
    qué atributo pertenece cada valor no se puede aplicar.

    Va por el contrato público y no metiendo el atributo dentro de
    `receta_item.aplica_valores`: la condición nombra valores que el cliente
    **no** eligió —"aplica si la mitad es Americana u Hawaiana"—, así que el
    dato no puede viajar en el evento de la venta, que solo lleva lo
    elegido. Denormalizarlo en la columna sería una segunda copia de algo
    que ya es único por construcción (un valor pertenece a una línea, y la
    línea a un atributo).

    Una consulta, no una por valor. Los ids que no existan simplemente no
    salen en el mapa, y `aplica_a_variante` los trata como huérfanos.
    """
    ids = [uuid.UUID(str(v)) for v in valor_ids]
    if not ids:
        return {}
    filas = session.execute(
        select(ProductoAtributoValor.id, ProductoAtributoLinea.atributo_id)
        .join(
            ProductoAtributoLinea,
            ProductoAtributoValor.linea_id == ProductoAtributoLinea.id,
        )
        .where(ProductoAtributoValor.id.in_(ids))
    )
    return {str(valor_id): str(atributo_id) for valor_id, atributo_id in filas}


def categoria_de_productos(
    session: Session, producto_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID | None]:
    """`producto_comercial_id` → `categoria_id`.

    La categoría es la **misma tabla** que la de los artículos
    (`inventory.categoria`): es el único punto donde lo que se compra y lo que
    se vende se agrupan igual, y por eso configurar ahí alcanza para repartir
    un asiento sin una segunda configuración del lado de ventas (ADR-086).
    """
    ids = {i for i in producto_ids if i is not None}
    if not ids:
        return {}
    filas = session.execute(
        select(ProductoComercial.id, ProductoComercial.categoria_id).where(
            ProductoComercial.id.in_(ids)
        )
    ).all()
    return dict(filas)


# --- Contrato del sitio de marca (storefront, ADR-101/RN-WEB-001..002) -----

def marca_de_producto(
    session: Session, producto_id: uuid.UUID
) -> uuid.UUID | None:
    """La `marca_id` de un producto comercial. `None` si no existe — lo usa
    `storefront` para validar que una foto se sube a un producto real antes
    de tocar S3."""
    return session.scalar(
        select(ProductoComercial.marca_id).where(ProductoComercial.id == producto_id)
    )


def marca_publica(session: Session, marca_id: uuid.UUID) -> dict | None:
    """Nombre de una marca, para el encabezado del sitio público. `None`
    si no existe o está borrada."""
    marca = session.scalar(
        select(Marca).where(Marca.id == marca_id, Marca.deleted_at.is_(None))
    )
    if marca is None:
        return None
    return {"id": marca.id, "nombre": marca.nombre}


def carta_publica(
    session: Session,
    *,
    marca_id: uuid.UUID,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
) -> list[dict]:
    """La carta que ve un cliente del sitio público: mismo motor de precio
    que el PDV (`precios.carta`), recortada a lo que RN-WEB-001 permite
    mostrar —sin extras, atributos ni exclusiones, que son detalle de
    configuración del PDV— y enriquecida con `descripcion`/`receta_id` por
    nodo, que `precios.carta` no trae porque el PDV nunca los necesitó.
    """
    # Import diferido: `precios` importa (transitivamente, vía
    # `inventory.application.recetas`) este mismo módulo — un import al
    # tope del archivo sería un ciclo. `carta_publica` es la única función
    # de este archivo que necesita `precios`.
    from src.modules.sales.application import precios

    items = precios.carta(
        session,
        sucursal_id=sucursal_id,
        canal=canal,
        modalidad=modalidad,
        marca_id=marca_id,
    )
    ids = {i["producto_comercial_id"] for i in items}
    for i in items:
        ids.update(v["producto_comercial_id"] for v in i.get("variantes", []))
    if not ids:
        return []
    filas = {
        p.id: p
        for p in session.scalars(
            select(ProductoComercial).where(ProductoComercial.id.in_(ids))
        )
    }

    def _nodo(item: dict) -> dict:
        producto = filas.get(item["producto_comercial_id"])
        return {
            "producto_comercial_id": item["producto_comercial_id"],
            "nombre": item["nombre"],
            "descripcion": producto.descripcion if producto else None,
            "receta_id": producto.receta_id if producto else None,
            "precio_unitario": item["precio_unitario"],
            "stock_bajo": item["stock_bajo"],
        }

    return [
        {
            **_nodo(item),
            "categoria_id": item["categoria_id"],
            "variantes": [
                _nodo(v) | {"orden": v.get("orden", 0)} for v in item.get("variantes", [])
            ],
        }
        for item in items
    ]


def promociones_web_vigentes(
    session: Session,
    *,
    empresa_ids: Sequence[uuid.UUID],
    marca_id: uuid.UUID,
    hoy: date,
) -> list[dict]:
    """Promociones (`sales.promocion`) con `"web"` en `canales`, vigentes
    hoy y con `marca_id` NULL o igual a la marca del sitio (RN-WEB-002).

    El filtro de `canales`/vigencia se hace en Python: `canales` es JSONB y
    el volumen de promociones activas por empresa es chico, mientras que la
    consulta equivalente se escribe distinto en SQLite y Postgres — mismo
    criterio que `ptav_usados_en_condiciones` de `inventory`.
    """
    if not empresa_ids:
        return []
    stmt = select(Promocion).where(
        Promocion.empresa_id.in_(list(empresa_ids)),
        Promocion.activa.is_(True),
        Promocion.deleted_at.is_(None),
        or_(Promocion.marca_id.is_(None), Promocion.marca_id == marca_id),
    )
    resultado = []
    for promo in session.scalars(stmt):
        if not promo.canales or "web" not in promo.canales:
            continue
        if promo.desde is not None and hoy < promo.desde:
            continue
        if promo.hasta is not None and hoy > promo.hasta:
            continue
        resultado.append(
            {
                "id": promo.id,
                "nombre": promo.nombre,
                "tipo": promo.tipo,
                "beneficio": promo.beneficio,
                "desde": promo.desde,
                "hasta": promo.hasta,
                "dias_semana": promo.dias_semana,
                "hora_desde": promo.hora_desde,
                "hora_hasta": promo.hora_hasta,
            }
        )
    return resultado


def ultimo_pedido_de_cliente(session: Session, cliente_id: uuid.UUID) -> dict | None:
    """El pedido más reciente de un cliente, para el "tu último pedido" del
    sitio de marca (ADR-102) — cualquier canal, no solo web (todavía no
    existe canal `web`; un cliente que ya compró en salón o delivery
    también quiere ver ese pedido al loguearse). `None` si nunca compró.
    """
    venta = session.scalar(
        select(Venta)
        .where(Venta.cliente_id == cliente_id, Venta.estado != "anulada")
        .order_by(Venta.created_at.desc())
        .limit(1)
    )
    if venta is None:
        return None
    items = session.execute(
        select(VentaItem.cantidad, ProductoComercial.nombre)
        .join(ProductoComercial, ProductoComercial.id == VentaItem.producto_comercial_id)
        .where(
            VentaItem.venta_id == venta.id,
            VentaItem.padre_venta_item_id.is_(None),
        )
    )
    return {
        "id": venta.id,
        "numero_orden": venta.numero_orden,
        "fecha_orden": venta.fecha_orden,
        "estado": venta.estado,
        "total": venta.total,
        "canal": venta.canal,
        "modalidad": venta.modalidad,
        "items": [{"nombre": nombre, "cantidad": cantidad} for cantidad, nombre in items],
    }
