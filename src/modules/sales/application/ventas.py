"""Casos de uso de venta: crear (= confirmar orden), cobrar, anular.

Una venta creada ya ES una Orden de Pedido (estado `orden`) y publica
`sales.venta_confirmada` — el carrito previo vive en el cliente (PDV/kiosk),
no en el servidor.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.sales.application import comprobantes, precios
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Pago, Venta, VentaItem
from src.modules.sales.infrastructure.repositories import (
    MedioPagoRepo,
    MesaRepo,
    PagoRepo,
    ProductoComercialRepo,
    VentaRepo,
)
from src.shared.models import Comprobante


def _armar_item(
    session: Session,
    it: dict,
    *,
    productos: ProductoComercialRepo,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    dia: date,
) -> tuple[VentaItem, dict]:
    """Valida un ítem del request y le resuelve el precio. Devuelve la fila y
    el detalle que viaja en `sales.venta_confirmada` para que inventory
    descuente."""
    prod = productos.get(it["producto_comercial_id"])
    if prod is None or not prod.activo:
        raise NoEncontrado(
            f"producto comercial {it['producto_comercial_id']} no encontrado"
        )
    cantidad = Decimal(str(it["cantidad"]))
    if cantidad <= 0:
        raise ReglaNegocio("cantidad de ítem debe ser > 0")
    if it.get("precio_unitario") is None:
        precio_unitario = precios.resolver_precio(
            session,
            producto=prod,
            sucursal_id=sucursal_id,
            canal=canal,
            modalidad=modalidad,
            fecha=dia,
        )
    else:
        precio_unitario = Decimal(str(it["precio_unitario"]))
    grupo = int(it.get("grupo_cobro") or rules.GRUPO_COBRO_UNICO)
    if grupo < 1:
        raise ReglaNegocio("grupo_cobro debe ser >= 1")
    fila = VentaItem(
        producto_comercial_id=prod.id,
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        # Los descuentos salen de listas promocionales, no del cliente
        # (RN-PRC-003); en replay viaja el que ya se aplicó.
        descuento=Decimal(str(it.get("descuento") or 0)),
        grupo_cobro=grupo,
    )
    # Empaque se descuenta solo en las modalidades configuradas (RN-EMP-003).
    con_empaque = bool(prod.empaque_id and modalidad in (prod.modalidades_empaque or []))
    detalle = {
        "receta_id": str(prod.receta_id),
        "cantidad": str(cantidad),
        "empaque_articulo_id": str(prod.empaque_id) if con_empaque else None,
    }
    return fila, detalle, prod


def _armar_extras(
    session: Session,
    padre: VentaItem,
    padre_prod,
    extras: list[dict],
    *,
    productos: ProductoComercialRepo,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    dia: date,
) -> tuple[list[VentaItem], list[dict]]:
    """Cada extra es una línea propia colgada del padre (RN-COM-021).

    Hereda `grupo_cobro` del padre a propósito: dividir la cuenta no puede
    dejar la pizza en una cuenta y su extra queso en otra.
    """
    if not extras:
        return [], []
    if padre_prod.es_extra:
        raise ReglaNegocio("un extra no admite extras")

    filas, detalles = [], []
    for ex in extras:
        extra_id = ex["producto_comercial_id"]
        vinculo = productos.admite_extra(padre_prod.id, extra_id)
        if vinculo is None:
            raise ReglaNegocio(
                f"{padre_prod.nombre} no admite el extra {extra_id}"
            )
        # `cantidad` es POR PLATO: "extra queso" en 2 pizzas son 2 porciones.
        # Se multiplica una sola vez, acá, para que el cobro y el consumo
        # salgan del mismo número — si se cobrara 1 y se descontaran 2, la
        # merma aparecería como faltante de inventario todos los días.
        por_plato = Decimal(str(ex.get("cantidad") or 1))
        if vinculo.maximo is not None and por_plato > vinculo.maximo:
            raise ReglaNegocio(
                f"el extra admite hasta {vinculo.maximo} por línea"
            )
        fila, detalle, prod = _armar_item(
            session,
            {
                **ex,
                "cantidad": por_plato * padre.cantidad,
                "grupo_cobro": padre.grupo_cobro,
            },
            productos=productos,
            sucursal_id=sucursal_id,
            canal=canal,
            modalidad=modalidad,
            dia=dia,
        )
        if not prod.es_extra:
            raise ReglaNegocio(f"{prod.nombre} no está marcado como extra")
        filas.append(fila)
        detalles.append(detalle)
    return filas, detalles


def _armar_lineas(
    session: Session,
    items: list[dict],
    *,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    dia: date,
) -> tuple[list[VentaItem], list[list[VentaItem]], list[dict]]:
    """Líneas padre, sus extras y el detalle que viaja a inventory.

    Los extras van aparte y no en `filas` porque `padre_venta_item_id`
    necesita el id del padre, que recién existe tras el flush.
    """
    productos = ProductoComercialRepo(session)
    filas: list[VentaItem] = []
    extras_por_padre: list[list[VentaItem]] = []
    detalle: list[dict] = []
    for it in items:
        fila, det, prod = _armar_item(
            session, it, productos=productos, sucursal_id=sucursal_id,
            canal=canal, modalidad=modalidad, dia=dia,
        )
        hijos, dets_hijos = _armar_extras(
            session, fila, prod, it.get("extras") or [],
            productos=productos, sucursal_id=sucursal_id,
            canal=canal, modalidad=modalidad, dia=dia,
        )
        filas.append(fila)
        extras_por_padre.append(hijos)
        detalle.append(det)
        detalle.extend(dets_hijos)
    return filas, extras_por_padre, detalle


def _validar_mesa(
    session: Session,
    mesa_id: uuid.UUID | None,
    *,
    sucursal_id: uuid.UUID,
    modalidad: str,
) -> None:
    if mesa_id is None:
        return
    if modalidad != "mesa":
        raise ReglaNegocio("solo la modalidad `mesa` admite mesa_id")
    mesa = MesaRepo(session).get(mesa_id)
    if mesa is None or mesa.deleted_at is not None or not mesa.activa:
        raise NoEncontrado("mesa no encontrada o inactiva")
    # Una mesa de otra sucursal en la orden rompe el mapa del salón.
    if mesa.sucursal_id != sucursal_id:
        raise ReglaNegocio("la mesa no pertenece a la sucursal de la venta")


def crear_venta(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    punto_venta_id: uuid.UUID,
    canal: str,
    modalidad: str,
    usuario_id: uuid.UUID,
    idempotency_key: str,
    items: list[dict],  # [{producto_comercial_id, cantidad}]
    cliente_id: uuid.UUID | None = None,
    referencia_atencion: str | None = None,
    mesa_id: uuid.UUID | None = None,
    comensales: int | None = None,
    id: uuid.UUID | None = None,
    fecha_orden: date | None = None,
    numero_orden: int | None = None,
) -> Venta:
    """`id`, `fecha_orden` y `numero_orden` los fija el cliente solo cuando
    la venta ya ocurrió en otro lado y se está reproduciendo acá: es el
    caso del hub de sucursal sincronizando lo que vendió durante un corte
    (ADR-009). Sin ellos la nube y el hub generarían identificadores
    distintos para la misma venta, y el número de orden que vio el cliente
    en su comanda no sería el de la nube.

    El **precio lo fija el servidor** contra `lista_precio` (RN-PRC-003): el
    PDV manda producto y cantidad, nunca el monto. `precio_unitario` en un
    ítem solo lo acepta ese mismo camino de replay — una venta que ya se
    cobró conserva el precio al que se cobró, aunque la promoción haya
    vencido entre el corte y la sincronización.
    """
    if canal not in rules.CANALES:
        raise ReglaNegocio(f"canal inválido: {canal}")
    if modalidad not in rules.MODALIDADES:
        raise ReglaNegocio(f"modalidad inválida: {modalidad}")
    if not items:
        raise ReglaNegocio("una venta requiere al menos un ítem")
    if comensales is not None and comensales <= 0:
        raise ReglaNegocio("comensales debe ser > 0")
    _validar_mesa(session, mesa_id, sucursal_id=sucursal_id, modalidad=modalidad)

    repo = VentaRepo(session)
    # Idempotencia: reintento del mismo request devuelve la venta existente.
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente
    if id is not None and repo.get(id) is not None:
        raise Conflicto(f"ya existe una venta con id {id} y otra idempotency_key")

    dia = fecha_orden or date.today()
    filas, extras_por_padre, detalle_evento = _armar_lineas(
        session, items, sucursal_id=sucursal_id, canal=canal,
        modalidad=modalidad, dia=dia,
    )

    venta = Venta(
        id=id or uuid.uuid4(),
        sucursal_id=sucursal_id,
        fecha_orden=dia,
        numero_orden=numero_orden or repo.siguiente_numero_orden(sucursal_id, dia),
        punto_venta_id=punto_venta_id,
        canal=canal,
        modalidad=modalidad,
        cliente_id=cliente_id,
        usuario_id=usuario_id,
        estado="orden",
        total=rules.total_venta(
            [
                (f.cantidad, f.precio_unitario, f.descuento)
                for f in [*filas, *(h for hijos in extras_por_padre for h in hijos)]
            ]
        ),
        idempotency_key=idempotency_key,
        referencia_atencion=referencia_atencion,
        mesa_id=mesa_id,
        comensales=comensales,
    )
    # ponytail: correlativo max+1; el UNIQUE (sucursal, fecha, numero) corta
    # la carrera — si dos cajas chocan, el cliente reintenta con la misma
    # idempotency_key. Secuencia por sucursal si el volumen lo pide.
    repo.add(venta)
    for fila in filas:
        fila.venta_id = venta.id
        session.add(fila)
    # Los extras se atan después del flush: `padre_venta_item_id` necesita
    # que la línea padre ya tenga id.
    session.flush()
    for fila, hijos in zip(filas, extras_por_padre, strict=True):
        for hijo in hijos:
            hijo.venta_id = venta.id
            hijo.padre_venta_item_id = fila.id
            session.add(hijo)
    session.flush()

    event_bus.publish(
        "sales.venta_confirmada",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(sucursal_id),
            "items": detalle_evento,
            "total": str(venta.total),
        },
    )
    return venta


def total_a_cobrar(session: Session, venta: Venta, grupo_cobro: int | None = None):
    """Lo que realmente debe pagarse: subtotal de las líneas menos la parte
    del descuento manual que le corresponde. Sin `grupo_cobro` es la venta
    entera; con él, solo esa cuenta.
    """
    repo = VentaRepo(session)
    todos = repo.items(venta.id)
    base = rules.total_venta(
        [(f.cantidad, f.precio_unitario, f.descuento) for f in todos]
    )
    if grupo_cobro is None:
        return base - rules.monto_descuento(
            venta.descuento_modo, venta.descuento_valor, base
        )
    filas = [f for f in todos if f.grupo_cobro == grupo_cobro]
    parcial = rules.total_venta(
        [(f.cantidad, f.precio_unitario, f.descuento) for f in filas]
    )
    return parcial - rules.descuento_prorrateado(
        venta.descuento_modo, venta.descuento_valor, base, parcial
    )


def aplicar_descuento(
    session: Session,
    *,
    venta_id: uuid.UUID,
    modo: str | None,
    valor: Decimal | None,
    motivo: str | None,
    autorizado_por: uuid.UUID,
) -> Venta:
    """Descuento manual sobre el total de la orden (RN-COM-017).

    `modo=None` lo quita. Exige motivo y autorizador porque el margen
    regalado tiene que poder explicarse en el reporte de descuentos: sin
    saber quién y por qué, el dato no sirve para nada.

    No confundir con las promociones por marca/sucursal (2da unidad a mitad
    de precio, etc.): esas son condicionales, automáticas y viven en un
    motor aparte todavía no construido.
    """
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if venta.estado != "orden":
        raise Conflicto(f"la venta está {venta.estado}; no admite cambios de descuento")

    if modo is None:
        venta.descuento_modo = None
        venta.descuento_valor = None
        venta.descuento_motivo = None
        venta.descuento_autorizado_por = None
        venta.total = total_a_cobrar(session, venta)
        return venta

    if modo not in rules.MODOS_DESCUENTO:
        raise ReglaNegocio(f"modo de descuento inválido: {modo}")
    if valor is None or valor <= 0:
        raise ReglaNegocio("el descuento debe ser > 0")
    if modo == "porcentaje" and valor > 100:
        raise ReglaNegocio("el descuento porcentual no puede superar 100")
    if motivo not in rules.MOTIVOS_DESCUENTO:
        raise ReglaNegocio(f"motivo de descuento inválido: {motivo}")

    venta.descuento_modo = modo
    venta.descuento_valor = valor
    venta.descuento_motivo = motivo
    venta.descuento_autorizado_por = autorizado_por
    # `venta.total` es siempre lo que el cliente debe pagar: si no se
    # sincroniza acá, el cierre de caja cuadraría contra un total irreal.
    venta.total = total_a_cobrar(session, venta)
    event_bus.publish(
        "sales.descuento_aplicado",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            "modo": modo,
            "valor": str(valor),
            "motivo": motivo,
            "autorizado_por": str(autorizado_por),
        },
    )
    return venta


def registrar_pago(
    session: Session,
    *,
    venta_id: uuid.UUID,
    medio_pago_id: uuid.UUID,
    monto: Decimal,
    idempotency_key: str,
    referencia_externa: str | None = None,
    grupo_cobro: int = rules.GRUPO_COBRO_UNICO,
    receptor_num_doc: str | None = None,
    receptor_nombre: str | None = None,
    id: uuid.UUID | None = None,
) -> tuple[Pago, Venta, Comprobante | None]:
    """El pago nace `confirmado` (PDV presencial). Pasarela con webhook de
    confirmación async = slice Izipay posterior.

    Al cubrirse el total se crea el `comprobante` en estado `pendiente`; el
    envío a SUNAT lo hace la cola (el tercer valor devuelto es lo que el
    router encola tras el commit).

    `id` explícito: mismo motivo que en `crear_venta` — un cobro hecho
    offline conserva su identificador al reproducirse en la nube (ADR-009).
    """
    repo = PagoRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if existente is not None:
        return existente, venta, None
    if id is not None and repo.get(id) is not None:
        raise Conflicto(f"ya existe un pago con id {id} y otra idempotency_key")

    if venta.estado not in ("orden",):
        raise Conflicto(f"la venta está {venta.estado}; no admite pagos")
    if MedioPagoRepo(session).get(medio_pago_id) is None:
        raise NoEncontrado("medio de pago no encontrado")
    if monto <= 0:
        raise ReglaNegocio("el monto debe ser > 0")

    venta_repo = VentaRepo(session)
    grupos = venta_repo.grupos_de_cobro(venta_id)
    if grupo_cobro not in grupos:
        raise NoEncontrado(f"la venta no tiene una cuenta {grupo_cobro}")

    total_grupo = total_a_cobrar(session, venta, grupo_cobro)
    confirmados = repo.confirmados(venta_id, grupo_cobro)
    if sum(confirmados, Decimal(0)) + monto > total_grupo:
        raise ReglaNegocio("el pago excede el saldo de la cuenta")

    pago = repo.add(
        Pago(
            id=id or uuid.uuid4(),
            venta_id=venta_id,
            medio_pago_id=medio_pago_id,
            monto=monto,
            grupo_cobro=grupo_cobro,
            idempotency_key=idempotency_key,
            referencia_externa=referencia_externa,
            estado="confirmado",
        )
    )
    if not rules.pagos_cubren_total(confirmados + [monto], total_grupo):
        return pago, venta, None

    comprobante = _cerrar_cuenta(
        session,
        venta,
        grupo_cobro=grupo_cobro,
        grupos=grupos,
        receptor_num_doc=receptor_num_doc,
        receptor_nombre=receptor_nombre,
    )
    return pago, venta, comprobante


def _cerrar_cuenta(
    session: Session,
    venta: Venta,
    *,
    grupo_cobro: int,
    grupos: list[int],
    receptor_num_doc: str | None,
    receptor_nombre: str | None,
) -> Comprobante:
    """La cuenta quedó cubierta: emite SU comprobante aunque otras cuentas
    de la misma venta sigan pendientes, y recién marca la venta como pagada
    cuando ninguna queda con saldo."""
    comprobante = comprobantes.crear_comprobante_pendiente(
        session,
        venta,
        grupo_cobro=grupo_cobro,
        receptor_num_doc=receptor_num_doc,
        receptor_nombre=receptor_nombre,
    )
    repo = PagoRepo(session)
    saldos = [
        total_a_cobrar(session, venta, g)
        - sum(repo.confirmados(venta.id, g), Decimal(0))
        for g in grupos
    ]
    if rules.venta_totalmente_pagada(saldos):
        venta.estado = "pagada"
        event_bus.publish(
            "sales.venta_pagada",
            {"venta_id": str(venta.id), "total": str(total_a_cobrar(session, venta))},
        )
    return comprobante


def listar_items(session: Session, venta_id: uuid.UUID) -> list[dict]:
    """Líneas de una venta con su nombre resuelto, extras anidados bajo su
    línea padre — como el cajero las ve, no como se guardan en la tabla."""
    filas = VentaRepo(session).items(venta_id)
    productos = ProductoComercialRepo(session)
    nombre_de = {
        f.producto_comercial_id: productos.get(f.producto_comercial_id).nombre
        for f in filas
    }
    hijos_de: dict[uuid.UUID, list[VentaItem]] = {}
    for f in filas:
        if f.padre_venta_item_id is not None:
            hijos_de.setdefault(f.padre_venta_item_id, []).append(f)
    return [
        {
            "id": f.id,
            "producto_comercial_id": f.producto_comercial_id,
            "nombre": nombre_de[f.producto_comercial_id],
            "cantidad": f.cantidad,
            "precio_unitario": f.precio_unitario,
            "grupo_cobro": f.grupo_cobro,
            "extras": [
                {
                    "id": e.id,
                    "producto_comercial_id": e.producto_comercial_id,
                    "nombre": nombre_de[e.producto_comercial_id],
                    "cantidad": e.cantidad,
                    "precio_unitario": e.precio_unitario,
                }
                for e in hijos_de.get(f.id, [])
            ],
        }
        for f in filas
        if f.padre_venta_item_id is None
    ]


def anular_lineas(
    session: Session,
    *,
    venta_id: uuid.UUID,
    venta_item_ids: list[uuid.UUID],
    autorizado_por: uuid.UUID,
    motivo: str,
) -> Venta:
    """Quita líneas de una orden ya enviada (RN-COM-020).

    Antes de enviar a cocina el pedido vive en el PDV y corregirlo no toca
    el servidor. Después sí: la comanda ya salió, el insumo ya se descontó,
    y hay que reponer lo que no se va a preparar. Por eso exige autorización
    de supervisor — es plata que sale del inventario.

    Una línea ya cobrada no se anula por esta vía: eso es nota de crédito.
    Quitar todas las líneas equivale a anular la orden completa.
    """
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if venta.estado != "orden":
        raise Conflicto(
            f"la venta está {venta.estado}; anular después del cobro requiere nota de crédito"
        )
    if not venta_item_ids:
        raise ReglaNegocio("indica al menos una línea a anular")
    if not (motivo or "").strip():
        raise ReglaNegocio("la anulación de línea requiere motivo")

    pedidos = set(venta_item_ids)
    filas = [f for f in VentaRepo(session).items(venta_id) if f.id in pedidos]
    if len(filas) != len(pedidos):
        raise NoEncontrado("alguna línea no pertenece a esta venta")

    productos = ProductoComercialRepo(session)
    devueltos = []
    for fila in filas:
        prod = productos.get(fila.producto_comercial_id)
        devueltos.append(
            {"receta_id": str(prod.receta_id), "cantidad": str(fila.cantidad)}
        )
        session.delete(fila)
    session.flush()

    restantes = VentaRepo(session).items(venta_id)
    venta.total = total_a_cobrar(session, venta)
    # Sin líneas no queda orden que preparar: la venta se anula entera.
    if not restantes:
        venta.estado = "anulada"

    event_bus.publish(
        "sales.lineas_anuladas",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            "autorizado_por": str(autorizado_por),
            "motivo": motivo,
            "items": devueltos,
        },
    )
    return venta


def anular_venta(session: Session, venta_id: uuid.UUID, usuario_id: uuid.UUID) -> Venta:
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if not rules.puede_anular(venta.estado):
        raise Conflicto(
            f"venta {venta.estado}: anulación post-pago requiere nota de crédito"
        )
    venta.estado = "anulada"
    productos = ProductoComercialRepo(session)
    items = []
    for it in VentaRepo(session).items(venta_id):
        prod = productos.get(it.producto_comercial_id)
        items.append({"receta_id": str(prod.receta_id), "cantidad": str(it.cantidad)})
    event_bus.publish(
        "sales.venta_anulada",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            "usuario_id": str(usuario_id),
            "items": items,
        },
    )
    return venta
