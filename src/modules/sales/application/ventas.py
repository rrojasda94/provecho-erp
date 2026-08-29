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
from src.modules.accounting.application.queries_publicas import hay_caja_abierta
from src.modules.inventory.application.queries_publicas import insumos_de_receta
from src.modules.sales.application import (
    catalogo,
    comprobantes,
    precios,
    promociones,
    tarifa_delivery,
)
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
from src.shared import auditoria, fechas
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
    gratis: bool = False,
    exigir_opciones: bool = True,
) -> tuple[VentaItem, dict]:
    """Valida un ítem del request y le resuelve el precio. Devuelve la fila y
    el detalle que viaja en `sales.venta_confirmada` para que inventory
    descuente.

    `gratis=True` (consumo de personal, RN-COM-025) no consulta lista de
    precios ni acepta el precio del cliente: la línea vale cero por
    definición, y un precio que viaje en el request no puede convertirla en
    venta."""
    prod = productos.get(it["producto_comercial_id"])
    if prod is None or not prod.activo:
        raise NoEncontrado(
            f"producto comercial {it['producto_comercial_id']} no encontrado"
        )
    # Un producto con variantes no se prepara ni se cobra: lo que se vende
    # es la variante (RN-COM-022). Sin receta no hay qué descontar, así que
    # dejarlo pasar vendería sin mover inventario.
    if prod.receta_id is None:
        raise ReglaNegocio(
            f"'{prod.nombre}' se vende por variante: elige tamaño/presentación"
        )
    cantidad = Decimal(str(it["cantidad"]))
    if cantidad <= 0:
        raise ReglaNegocio("cantidad de ítem debe ser > 0")
    restas = _resolver_restas(
        session, prod, it.get("sin_articulo_ids"), exigir=exigir_opciones
    )
    # Se resuelve antes del precio porque el recargo del valor elegido entra
    # en él (RN-COM-036).
    valores = _resolver_valores_variante(
        session, prod, it.get("valores_variante_ids"), exigir=exigir_opciones
    )
    if gratis:
        precio_unitario = Decimal(0)
    elif it.get("precio_unitario") is None:
        precio_unitario = precios.resolver_precio(
            session,
            producto=prod,
            sucursal_id=sucursal_id,
            canal=canal,
            modalidad=modalidad,
            fecha=dia,
        ) + precios.recargo_de_valores(session, valores)
    else:
        # Precio provisto: el replay del hub trae lo que YA se cobró y no se
        # recotiza (ADR-009). Sumarle el recargo acá lo cobraría dos veces.
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
        descuento=Decimal(0) if gratis else Decimal(str(it.get("descuento") or 0)),
        grupo_cobro=grupo,
        sin_articulo_ids=restas,
        valores_variante_ids=valores,
        # Texto libre para cocina. Se normaliza a `None` cuando llega vacío:
        # el PDV manda `""` con solo abrir el diálogo, y una nota vacía en el
        # KDS es una línea de más que el cocinero lee y descarta.
        nota=(it.get("nota") or "").strip() or None,
        # Solo el replay del hub la manda (ADR-009): la venta ya se preparó
        # allá y sus tandas son las que la cocina vio. En el alta normal todo
        # es la tanda 1, y `agregar_lineas` la pisa con la del envío.
        tanda=int(it.get("tanda") or 1),
    )
    # Empaque se descuenta solo en las modalidades configuradas (RN-EMP-003).
    con_empaque = bool(prod.empaque_id and modalidad in (prod.modalidades_empaque or []))
    detalle = {
        "receta_id": str(prod.receta_id),
        "cantidad": str(cantidad),
        "empaque_articulo_id": str(prod.empaque_id) if con_empaque else None,
        "sin_articulo_ids": restas,
        # Aditivo (ADR-056): un consumidor que lo ignore se comporta como
        # antes, igual que pasó con `sin_articulo_ids` en ADR-035.
        "valores_variante_ids": valores,
    }
    return fila, detalle, prod


def _resolver_valores_variante(
    session: Session, prod, pedidos, *, exigir: bool
) -> list[str] | None:
    """Qué valores de atributo eligió esta línea (ADR-055/056).

    Solo se aceptan valores que el producto **o su padre** ofrecen. La
    herencia es la misma regla que ADR-042 fijó para grupos y extras, y por
    la misma razón: dónde quedó colgado el atributo no debería decidir
    nada, y mientras eso importe siempre hay una mitad de los catálogos
    rota — el que arma una persona cuelga del padre, el que genera el
    importador cuelga de la variante.

    Rechazar en vez de ignorar: un valor ajeno no es inocuo, porque puede
    activar líneas de receta condicionadas y mover stock que nadie pidió.

    Y se rechaza también la **combinación imposible** que declara
    `producto_exclusion`: media hawaiana y media hawaiana no es una
    mitad-y-mitad, es una hawaiana entera —que ya se vende como su propio
    producto, con su receta y su precio—. Que la pantalla no la ofrezca no
    alcanza: el kiosko y la central de pedidos entran por este mismo
    endpoint, y una regla que solo vive en una pantalla no es una regla
    (mismo criterio que `_validar_grupos`, ADR-023 §2).

    `exigir=False` en el replay del hub (ADR-009), mismo criterio que las
    restas: esa venta ya se preparó y se cobró, y el catálogo pudo cambiar
    durante el corte.
    """
    if not pedidos:
        return None
    ids = list(dict.fromkeys(str(v) for v in pedidos))
    if not exigir:
        return ids
    ofrecidos = catalogo.valores_ofrecidos(session, prod)
    ajenos = [v for v in ids if v not in ofrecidos]
    if ajenos:
        raise ReglaNegocio(
            f"'{prod.nombre}' no ofrece {len(ajenos)} de los valores "
            "elegidos: solo se puede elegir lo que el producto declara"
        )
    choque = catalogo.combinacion_excluida(session, ids)
    if choque:
        izquierda, derecha = choque
        if izquierda == derecha:
            raise ReglaNegocio(
                f"'{prod.nombre}' lleva dos mitades distintas: «{izquierda}» "
                "no se puede elegir en las dos"
            )
        raise ReglaNegocio(
            f"'{prod.nombre}' no admite «{izquierda}» junto con «{derecha}»"
        )
    return ids


def _resolver_restas(
    session: Session, prod, pedidas, *, exigir: bool
) -> list[str] | None:
    """Qué insumos NO lleva esta línea ("sin cebolla", RN-PRD-004).

    Solo se puede quitar lo que la receta pone: pedir "sin palta" en una
    pizza que no lleva palta no es inocuo —el PDV mostraría una resta que
    cocina no puede cumplir y el reporte contaría un ajuste que nunca
    existió—, así que se rechaza en vez de ignorarse. La lista de quitables
    no se configura: **es** la lista de insumos de la receta.

    `exigir=False` en el replay del hub (ADR-009): esa venta ya se preparó y
    se cobró, y la receta pudo cambiar durante el corte. Se guarda lo que
    viene tal cual — rechazarla ahora perdería una venta real, y una resta
    que ya no calza con la receta simplemente no descuenta nada de menos.
    """
    if not pedidas:
        return None
    # `dict.fromkeys` y no `set`: quita repetidos conservando el orden en que
    # el mozo los tecleó, que es el orden en que cocina los va a leer.
    ids = list(dict.fromkeys(str(a) for a in pedidas))
    if not exigir:
        return ids
    insumos = {
        str(i["articulo_id"]) for i in insumos_de_receta(session, prod.receta_id)
    }
    ajenos = [a for a in ids if a not in insumos]
    if ajenos:
        raise ReglaNegocio(
            f"'{prod.nombre}' no lleva {len(ajenos)} de los insumos que se "
            "piden quitar: solo se puede quitar lo que la receta pone"
        )
    return ids


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
    exigir_opciones: bool = True,
    gratis: bool = False,
) -> tuple[list[VentaItem], list[dict]]:
    """Cada extra es una línea propia colgada del padre (RN-COM-021).

    Hereda `grupo_cobro` del padre a propósito: dividir la cuenta no puede
    dejar la pizza en una cuenta y su extra queso en otra.

    `exigir_opciones=False` en el replay del hub (ADR-009), mismo criterio
    que en la línea padre: el extra ya se preparó y se cobró, y el vínculo
    con el plato pudo desarmarse durante el corte. Se guarda lo que viene.
    """
    if not extras:
        return [], []
    if padre_prod.es_extra:
        raise ReglaNegocio("un extra no admite extras")

    filas, detalles = [], []
    for ex in extras:
        extra_id = ex["producto_comercial_id"]
        # `cantidad` es POR PLATO: "extra queso" en 2 pizzas son 2 porciones.
        # Se multiplica una sola vez, acá, para que el cobro y el consumo
        # salgan del mismo número — si se cobrara 1 y se descontaran 2, la
        # merma aparecería como faltante de inventario todos los días.
        por_plato = Decimal(str(ex.get("cantidad") or 1))
        if exigir_opciones:
            # Efectivo: incluye lo heredado del padre (ADR-042). Rechazar un
            # extra que la carta acaba de ofrecer manda al cajero a un error
            # que no puede corregir desde la pantalla que se lo ofreció.
            vinculo = productos.admite_extra_efectivo(padre_prod, extra_id)
            if vinculo is None:
                raise ReglaNegocio(
                    f"{padre_prod.nombre} no admite el extra {extra_id}"
                )
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
            exigir_opciones=exigir_opciones,
            gratis=gratis,
        )
        if exigir_opciones and not prod.es_extra:
            raise ReglaNegocio(f"{prod.nombre} no está marcado como extra")
        filas.append(fila)
        detalles.append(detalle)
    return filas, detalles


def _validar_grupos(
    productos: ProductoComercialRepo, prod, extras: list[dict]
) -> None:
    """Cuántas opciones exige cada grupo del producto (RN-COM-023).

    Se valida en el servidor y no solo en el PDV porque el kiosko, la
    central de pedidos y cualquier integración futura entran por el mismo
    endpoint: una regla que solo vive en una pantalla no es una regla.
    """
    grupos = productos.grupos_efectivos(prod)
    if not grupos:
        return
    elegidos: dict[uuid.UUID, int] = {}
    for ex in extras:
        vinculo = productos.admite_extra_efectivo(prod, ex["producto_comercial_id"])
        if vinculo is not None and vinculo.grupo_id is not None:
            elegidos[vinculo.grupo_id] = elegidos.get(vinculo.grupo_id, 0) + 1
    for grupo in grupos:
        cuantos = elegidos.get(grupo.id, 0)
        if cuantos < grupo.minimo:
            raise ReglaNegocio(
                f"'{prod.nombre}': '{grupo.nombre}' exige elegir "
                f"{grupo.minimo}, llegaron {cuantos}"
            )
        if grupo.maximo is not None and cuantos > grupo.maximo:
            raise ReglaNegocio(
                f"'{prod.nombre}': '{grupo.nombre}' admite hasta {grupo.maximo}"
            )


def _validar_atributos(session: Session, prod, valores: list[str] | None) -> None:
    """Un producto que ofrece atributos no se vende sin elegir un valor de
    cada uno (RN-COM-040).

    Importa porque la elección es lo que activa las líneas condicionadas de
    la receta (`receta_item.aplica_valores`, RN-COM-037): una MitadXMitad
    cobrada sin sabores se prepara igual pero **no descuenta ningún insumo**,
    y el faltante recién aparece en el conteo del mes. Antes esto pasaba en
    silencio — `_resolver_valores_variante` devuelve `None` cuando no llega
    nada, que es correcto para una venta vieja pero no para una nueva.

    Se hace cumplir acá y no solo en el PDV porque el kiosko, la central de
    pedidos y cualquier integración futura entran por el mismo endpoint.

    La oferta sale de `catalogo.atributos_ofrecidos`, **la misma** función que
    alimenta la carta: si el filtro se escribiera dos veces, la pantalla no
    ofrecería lo que este validador exige y el producto quedaría invendible.
    """
    ofrecidos = catalogo.atributos_ofrecidos(session, [prod]).get(prod.id)
    if not ofrecidos:
        return
    elegidos = {str(v) for v in (valores or [])}
    for atributo in ofrecidos:
        posibles = {str(v["id"]) for v in atributo["valores"]}
        if not posibles & elegidos:
            raise ReglaNegocio(
                f"'{prod.nombre}': falta elegir {atributo['nombre']}"
            )


def _armar_lineas(
    session: Session,
    items: list[dict],
    *,
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    dia: date,
    exigir_opciones: bool = True,
    gratis: bool = False,
) -> tuple[list[VentaItem], list[list[VentaItem]], list[dict]]:
    """Líneas padre, sus extras y el detalle que viaja a inventory.

    Los extras van aparte y no en `filas` porque `padre_venta_item_id`
    necesita el id del padre, que recién existe tras el flush.

    `exigir_opciones=False` en el replay del hub (ADR-009): la venta ya
    ocurrió y se cobró: rechazarla ahora porque alguien volvió obligatorio
    un grupo durante el corte perdería una venta real.
    """
    productos = ProductoComercialRepo(session)
    filas: list[VentaItem] = []
    extras_por_padre: list[list[VentaItem]] = []
    detalle: list[dict] = []
    for it in items:
        fila, det, prod = _armar_item(
            session, it, productos=productos, sucursal_id=sucursal_id,
            canal=canal, modalidad=modalidad, dia=dia, gratis=gratis,
            exigir_opciones=exigir_opciones,
        )
        if exigir_opciones:
            _validar_grupos(productos, prod, it.get("extras") or [])
            _validar_atributos(session, prod, it.get("valores_variante_ids"))
        hijos, dets_hijos = _armar_extras(
            session, fila, prod, it.get("extras") or [],
            productos=productos, sucursal_id=sucursal_id,
            canal=canal, modalidad=modalidad, dia=dia,
            exigir_opciones=exigir_opciones, gratis=gratis,
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
    if mesa is None or not mesa.activa:
        raise NoEncontrado("mesa no encontrada o inactiva")
    # Una mesa de otra sucursal en la orden rompe el mapa del salón.
    if mesa.sucursal_id != sucursal_id:
        raise ReglaNegocio("la mesa no pertenece a la sucursal de la venta")


def _abrir_mesa_para_traslado(
    session: Session, origen: Venta, *, mesa_id: uuid.UUID, comensales: int | None
) -> Venta:
    """Abre la orden destino de un traslado a una mesa libre.

    No pasa por `crear_venta`: ese camino publica `sales.venta_confirmada` y
    descontaría el inventario que estas líneas ya consumieron cuando se armó
    la orden origen (RN-COM-043 — mover no es vender de nuevo).
    """
    _validar_mesa(session, mesa_id, sucursal_id=origen.sucursal_id, modalidad="mesa")
    dia = fechas.hoy()
    ocupada = any(
        v.mesa_id == mesa_id
        for v in MesaRepo(session).ocupadas(origen.sucursal_id, dia)
    )
    if ocupada:
        raise Conflicto("la mesa ya tiene una orden abierta")
    repo = VentaRepo(session)
    destino = Venta(
        id=uuid.uuid4(),
        sucursal_id=origen.sucursal_id,
        fecha_orden=dia,
        numero_orden=repo.siguiente_numero_orden(origen.sucursal_id, dia),
        punto_venta_id=origen.punto_venta_id,
        canal=origen.canal,
        modalidad="mesa",
        usuario_id=origen.usuario_id,
        estado="orden",
        total=Decimal("0"),
        idempotency_key=f"mover:{uuid.uuid4()}",
        mesa_id=mesa_id,
        comensales=comensales,
        tipo=origen.tipo,
    )
    return repo.add(destino)


def _validar_tipo(
    tipo: str, consumo_motivo: str | None, autorizado_por: uuid.UUID | None
) -> bool:
    """Devuelve si la orden es consumo de personal, validándolo (RN-COM-025).

    Un motivo suelto en una venta normal no se ignora: quien lo mandó creía
    estar registrando comida del personal y en realidad estaba cobrándola.
    """
    if tipo not in rules.TIPOS_VENTA:
        raise ReglaNegocio(f"tipo de venta inválido: {tipo}")
    if not rules.es_consumo_personal(tipo):
        if consumo_motivo is not None:
            raise ReglaNegocio("`consumo_motivo` solo aplica al consumo de personal")
        return False
    if consumo_motivo not in rules.MOTIVOS_CONSUMO_PERSONAL:
        raise ReglaNegocio(
            f"motivo de consumo de personal inválido: {consumo_motivo}"
        )
    if autorizado_por is None:
        raise ReglaNegocio(
            "el consumo de personal requiere autorización de un encargado"
        )
    return True


def _cotizar_entrega(
    session: Session,
    sucursal_id: uuid.UUID,
    modalidad: str,
    direccion_entrega: str | None,
    lat: Decimal | None,
    lng: Decimal | None,
    distrito: str | None,
    ya_cotizado: bool = False,
):
    """Cotiza el reparto, o `None` si este pedido no se lleva a ningún lado.

    Mesa y takeout no pagan reparto, y un delivery sin dirección tampoco se
    puede medir: en los dos casos la venta se crea sin costo de entrega, que
    es como funcionaba antes de ADR-054.

    `ya_cotizado` es el replay del hub: esa venta ya se cobró con un
    precio, y recalcularlo acá lo cambiaría a espaldas del cliente.
    """
    if ya_cotizado or modalidad != "delivery" or not direccion_entrega:
        return None
    origen, empresa_id = tarifa_delivery.contexto_de_sucursal(session, sucursal_id)
    return tarifa_delivery.cotizar(
        origen,
        tarifa_delivery.coordenada(lat, lng),
        distrito,
        tarifa_delivery.tarifa_de(session, empresa_id),
    )


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
    direccion_entrega: str | None = None,
    ubicacion_place_id: str | None = None,
    ubicacion_lat: Decimal | None = None,
    ubicacion_lng: Decimal | None = None,
    ubicacion_plus_code: str | None = None,
    ubicacion_distrito: str | None = None,
    # Solo en el replay del hub: la venta ya se cotizó allá y ese es el
    # precio que se le cobró al cliente. Volver a preguntarle a Google
    # daría otro número y una llamada de más.
    distancia_entrega_km: Decimal | None = None,
    costo_entrega: Decimal | None = None,
    mesa_id: uuid.UUID | None = None,
    comensales: int | None = None,
    nota_cocina: str | None = None,
    id: uuid.UUID | None = None,
    fecha_orden: date | None = None,
    numero_orden: int | None = None,
    tipo: str = "venta",
    consumo_motivo: str | None = None,
    consumo_autorizado_por: uuid.UUID | None = None,
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

    `tipo="consumo_personal"` es la comida del personal (RN-COM-025): se
    prepara y despacha igual, pero **todas sus líneas valen cero**, no se
    cobra y no emite comprobante. Exige motivo y el encargado que lo
    autorizó con su PIN, y publica su propio evento —no
    `sales.venta_confirmada`— porque no es ingreso ni atribuible a una
    campaña; su costo es gasto de alimentación de personal.
    """
    if canal not in rules.CANALES:
        raise ReglaNegocio(f"canal inválido: {canal}")
    if modalidad not in rules.MODALIDADES:
        raise ReglaNegocio(f"modalidad inválida: {modalidad}")
    consumo = _validar_tipo(tipo, consumo_motivo, consumo_autorizado_por)
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

    dia = fecha_orden or fechas.hoy()
    filas, extras_por_padre, detalle_evento = _armar_lineas(
        session, items, sucursal_id=sucursal_id, canal=canal,
        modalidad=modalidad, dia=dia,
        # Replay del hub: la venta ya ocurrió (trae su número de orden), no
        # se la vuelve a validar contra reglas que pudieron cambiar.
        exigir_opciones=numero_orden is None,
        gratis=consumo,
    )

    # Se cotiza acá y no en el navegador: este número define cuánta plata
    # paga el cliente. Se congela en la fila (ADR-054) — la tarifa por
    # kilómetro cambia y el pedido de ayer no puede cambiar de precio.
    cotizacion = _cotizar_entrega(
        session,
        sucursal_id,
        modalidad,
        direccion_entrega,
        ubicacion_lat,
        ubicacion_lng,
        ubicacion_distrito,
        ya_cotizado=costo_entrega is not None,
    )
    reparto = cotizacion.costo if cotizacion else costo_entrega
    # El flete entra al total desde el minuto cero (RN-COM-041). Acá se suma
    # a mano porque la fila todavía no existe y `total_a_cobrar` necesita una:
    # es el único lugar donde el total se arma sin pasar por esa función.
    flete = (reparto or Decimal("0")) if rules.admite_cobro(tipo) else Decimal("0")

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
        )
        + flete,
        idempotency_key=idempotency_key,
        referencia_atencion=referencia_atencion,
        direccion_entrega=direccion_entrega,
        ubicacion_place_id=ubicacion_place_id,
        ubicacion_lat=ubicacion_lat,
        ubicacion_lng=ubicacion_lng,
        ubicacion_plus_code=ubicacion_plus_code,
        ubicacion_distrito=ubicacion_distrito,
        distancia_entrega_km=(
            cotizacion.distancia_km if cotizacion else distancia_entrega_km
        ),
        costo_entrega=reparto,
        mesa_id=mesa_id,
        comensales=comensales,
        nota_cocina=(nota_cocina or "").strip() or None,
        tipo=tipo,
        consumo_motivo=consumo_motivo,
        consumo_autorizado_por=consumo_autorizado_por,
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

    # Las promociones se evalúan con las líneas ya en la base y **antes** de
    # anunciar la venta: el evento lleva `total`, y accounting asienta lo que
    # el cliente paga, no el precio de lista (ADR-076).
    promociones.recalcular_promociones(session, venta)
    venta.total = total_a_cobrar(session, venta)

    _confirmar(
        session,
        venta,
        detalle_evento=detalle_evento,
        consumo=consumo,
        registrado_por=usuario_id,
    )
    return venta


def _confirmar(
    session: Session,
    venta: Venta,
    *,
    detalle_evento: list[dict],
    consumo: bool,
    registrado_por: uuid.UUID,
    total: Decimal | None = None,
) -> None:
    """Anuncia la orden confirmada. Un consumo de personal publica su propio
    evento: no es ingreso para contabilidad ni venta atribuible para
    marketing, y su costo va a gasto (RN-COM-025).

    `total` es **lo confirmado en esta operación**, no el acumulado de la
    venta. Al crearla son lo mismo; al agregar líneas a una orden ya enviada
    (RN-COM-029) es el incremento, que es lo que accounting tiene que
    asentar — mandarle el total completo lo asentaría dos veces. `items` ya
    era el detalle de la operación, así que las dos claves dicen lo mismo.
    """
    payload = {
        "venta_id": str(venta.id),
        "sucursal_id": str(venta.sucursal_id),
        "cliente_id": str(venta.cliente_id) if venta.cliente_id else None,
        "items": detalle_evento,
        "total": str(venta.total if total is None else total),
    }
    if not consumo:
        event_bus.publish("sales.venta_confirmada", payload, session=session)
        return
    # Comida regalada: quién la autorizó tiene que quedar escrito aunque
    # nadie mire el evento (ADR-031).
    auditoria.registrar(
        session,
        usuario_id=venta.consumo_autorizado_por,
        entidad="venta",
        entidad_id=venta.id,
        accion="autorizar_consumo_personal",
        datos_despues={
            "motivo": venta.consumo_motivo,
            "numero_orden": venta.numero_orden,
            "registrado_por": str(registrado_por),
        },
        sucursal_id=venta.sucursal_id,
    )
    event_bus.publish(
        "sales.consumo_personal_registrado",
        {**payload, "tipo": venta.tipo, "consumo_motivo": venta.consumo_motivo},
        session=session,
    )


def _subtotal(items: list[VentaItem]) -> Decimal:
    return rules.total_venta(
        [(f.cantidad, f.precio_unitario, f.descuento) for f in items]
    )


def reparto_a_cobrar(venta: Venta) -> Decimal:
    """El flete que entra al total (RN-COM-041).

    Un consumo de personal vale cero entero: cobrarle el reparto a un
    trabajador que se lleva su almuerzo emitiría un comprobante por el flete
    solo, que es peor que no cobrarlo.
    """
    if not rules.admite_cobro(venta.tipo):
        return Decimal("0")
    return venta.costo_entrega or Decimal("0")


def total_a_cobrar(session: Session, venta: Venta, grupo_cobro: int | None = None):
    """Lo que realmente debe pagarse: subtotal de las líneas menos las
    promociones y la parte del descuento manual que le corresponde, más el
    reparto. Sin `grupo_cobro` es la venta entera; con él, solo esa cuenta.

    **El reparto se suma después del descuento** (RN-COM-041): el descuento
    manual lo autoriza un encargado sobre lo que el cliente consumió, y
    regalar el flete al mismo tiempo no es lo que se aprobó.

    **Las promociones bajan antes que el descuento manual** (ADR-076): el
    supervisor firma un porcentaje sobre lo que el cliente va a pagar, no
    sobre el precio de lista de algo que la promoción ya rebajó. Al revés,
    un 20 % firmado sobre un pedido con 2x1 regalaría casi la mitad del
    ticket sin que nadie lo haya aprobado así.
    """
    todos = VentaRepo(session).items(venta.id)
    base = _subtotal(todos) - promociones.total_aplicado(session, venta.id)
    reparto = reparto_a_cobrar(venta)
    if grupo_cobro is None:
        neto = base - rules.monto_descuento(
            venta.descuento_modo, venta.descuento_valor, base
        )
        return rules.a_centavos(neto + reparto)
    filas = [f for f in todos if f.grupo_cobro == grupo_cobro]
    # La promoción se prorratea entre las cuentas por lo que pesa cada una,
    # igual que el descuento manual: se activó sobre el pedido, no sobre la
    # cuenta que toque cobrarse primero.
    bruto_total = _subtotal(todos)
    parcial_bruto = _subtotal(filas)
    parcial = (
        parcial_bruto
        if bruto_total <= 0
        else (base * parcial_bruto / bruto_total).quantize(Decimal("0.01"))
    )
    # El flete **no se prorratea**: va entero en la primera cuenta. Repartir
    # un reparto entre comensales es un caso que nadie pidió, pero omitirlo
    # sí rompía algo real — el cobro normal del PDV pasa por acá con
    # `grupo_cobro=1`, así que sin esto el delivery de una sola cuenta no se
    # cobraba nunca. La suma de las cuentas tiene que dar el total de la
    # venta, o `pagos_cubren_total` deja la orden sin poder cerrarse.
    grupos = VentaRepo(session).grupos_de_cobro(venta.id)
    if grupo_cobro != min(grupos, default=rules.GRUPO_COBRO_UNICO):
        reparto = Decimal("0")
    return rules.a_centavos(
        parcial
        - rules.descuento_prorrateado(
            venta.descuento_modo, venta.descuento_valor, base, parcial
        )
        + reparto
    )


def calcular_monto_descuento(
    session: Session, venta: Venta, modo: str | None, valor: Decimal | None
) -> Decimal:
    """Cuánto descontaría `modo`/`valor` sobre lo que hoy se paga — sin
    aplicarlo. El router lo usa para validar `permiso.restricciones`
    (ADR-023, `monto_maximo`) ANTES de comprometer el cambio.

    La base descuenta las promociones ya activadas (ADR-076): el tope del
    supervisor tiene que medirse contra lo que de verdad se va a regalar."""
    base = _subtotal(VentaRepo(session).items(venta.id)) - promociones.total_aplicado(
        session, venta.id
    )
    return rules.monto_descuento(modo, valor, base)


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
    if not rules.admite_cobro(venta.tipo):
        raise Conflicto("un consumo de personal ya vale cero: no admite descuento")

    if modo is None:
        auditoria.registrar(
            session,
            usuario_id=autorizado_por,
            entidad="venta",
            entidad_id=venta.id,
            accion="descuento_quitado",
            datos_antes={
                "modo": venta.descuento_modo,
                "valor": str(venta.descuento_valor or ""),
                "motivo": venta.descuento_motivo,
            },
            sucursal_id=venta.sucursal_id,
        )
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

    auditoria.registrar(
        session,
        usuario_id=autorizado_por,
        entidad="venta",
        entidad_id=venta.id,
        accion="descuento_aplicado",
        datos_antes={"total": str(venta.total)},
        datos_despues={"modo": modo, "valor": str(valor), "motivo": motivo},
        sucursal_id=venta.sucursal_id,
    )
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
        session=session,
    )
    return venta


def _validar_cobro(
    session: Session,
    venta: Venta,
    *,
    medio_pago_id: uuid.UUID,
    monto: Decimal,
    exigir_caja_abierta: bool,
) -> None:
    """Lo que tiene que ser cierto antes de aceptar plata.

    El candado de caja (RN-MDP-002): la plata cobrada fuera de un turno no
    la espera ningún cierre, así que el faltante aparece recién en
    contabilidad y ya sin responsable (RN-MDP-005). Se pregunta por el
    contrato público de `accounting`; `sales` nunca ve `AperturaCaja`.
    """
    if venta.estado not in ("orden",):
        raise Conflicto(f"la venta está {venta.estado}; no admite pagos")
    # Un consumo de personal no se cobra ni se factura (RN-COM-025): dejarlo
    # pasar acá terminaría emitiendo un comprobante de S/ 0.00 a SUNAT.
    if not rules.admite_cobro(venta.tipo):
        raise Conflicto("un consumo de personal no se cobra")
    if exigir_caja_abierta and not hay_caja_abierta(session, venta.punto_venta_id):
        raise Conflicto(
            "no hay caja abierta en este punto de venta: abre el turno antes "
            "de cobrar (RN-MDP-002)"
        )
    if MedioPagoRepo(session).get(medio_pago_id) is None:
        raise NoEncontrado("medio de pago no encontrado")
    if monto <= 0:
        raise ReglaNegocio("el monto debe ser > 0")


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
    exigir_caja_abierta: bool = True,
) -> tuple[Pago, Venta, Comprobante | None]:
    """El pago nace `confirmado` (PDV presencial). Pasarela con webhook de
    confirmación async = slice Izipay posterior.

    Al cubrirse el total se crea el `comprobante` en estado `pendiente`; el
    envío a SUNAT lo hace la cola (el tercer valor devuelto es lo que el
    router encola tras el commit).

    **No se cobra sin caja abierta** en el punto de venta: la plata cobrada
    fuera de un turno no la espera ningún cierre, así que el faltante recién
    aparece en contabilidad y ya no tiene responsable (RN-MDP-005). Se
    consulta por el contrato público de `accounting`, no importando su
    dominio.

    `exigir_caja_abierta=False` es solo para el **replay del hub** (ADR-009):
    el cobro ya ocurrió en la sucursal con su caja abierta, y volver a
    exigirla en la nube rechazaría una venta que físicamente pasó.

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

    _validar_cobro(
        session,
        venta,
        medio_pago_id=medio_pago_id,
        monto=monto,
        exigir_caja_abierta=exigir_caja_abierta,
    )

    venta_repo = VentaRepo(session)
    grupos = venta_repo.grupos_de_cobro(venta_id)
    if grupo_cobro not in grupos:
        raise NoEncontrado(f"la venta no tiene una cuenta {grupo_cobro}")

    total_grupo = total_a_cobrar(session, venta, grupo_cobro)
    confirmados = repo.confirmados(venta_id, grupo_cobro)
    saldo = rules.a_centavos(total_grupo - sum(confirmados, Decimal(0)))
    recibido = rules.a_centavos(monto)

    # Recibir más de lo que se debe solo es un error cuando el medio no puede
    # devolver la diferencia (ADR-077). En efectivo es el caso normal de una
    # caja —un billete de 50 por una cuenta de 33.30— y rechazarlo obligaba
    # al cajero a teclear el saldo exacto de memoria; en tarjeta no hay
    # vuelto posible y aceptarlo solo descuadraría el arqueo.
    medio = MedioPagoRepo(session).get(medio_pago_id)
    if recibido > saldo and not rules.admite_vuelto(medio.tipo):
        raise ReglaNegocio(
            "el pago excede el saldo de la cuenta y este medio no da vuelto"
        )
    # Lo que entra a la cuenta nunca pasa del saldo: la diferencia sale por
    # el cajón como vuelto, no queda asentada como plata cobrada.
    aplicado = min(recibido, saldo)
    vuelto = rules.vuelto_de(recibido, saldo)

    pago = repo.add(
        Pago(
            id=id or uuid.uuid4(),
            venta_id=venta_id,
            medio_pago_id=medio_pago_id,
            monto=aplicado,
            vuelto=vuelto,
            grupo_cobro=grupo_cobro,
            idempotency_key=idempotency_key,
            referencia_externa=referencia_externa,
            estado="confirmado",
        )
    )
    if not rules.pagos_cubren_total(confirmados + [aplicado], total_grupo):
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
            session=session,
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
            "descuento": f.descuento,
            "grupo_cobro": f.grupo_cobro,
            "nota": f.nota,
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


def _con_sus_extras(filas: list[VentaItem], todas: list[VentaItem]) -> list[VentaItem]:
    """Quitar un plato se lleva sus extras (RN-CUP-014).

    El PDV manda solo el id del plato. Sin esto pasaban dos cosas: el insumo
    del sabor no volvía al almacén, y borrar el padre dejaba al hijo
    apuntándolo — `fk_venta_item_padre` es NO ACTION, o sea
    `ForeignKeyViolation` en Postgres.
    """
    padres = {f.id for f in filas}
    pedidas = {f.id for f in filas}
    return filas + [
        f for f in todas if f.padre_venta_item_id in padres and f.id not in pedidas
    ]


def _a_reponer(session: Session, filas: list[VentaItem]) -> list[dict]:
    """Qué devolverle al almacén por cada línea que se quita."""
    productos = ProductoComercialRepo(session)
    return [
        {
            "receta_id": str(productos.get(f.producto_comercial_id).receta_id),
            "cantidad": str(f.cantidad),
            # Se repone exactamente lo que se consumió: lo que la línea no
            # llevó tampoco vuelve al almacén. Vale igual para la
            # combinación: reponer una línea de receta que la variante
            # elegida nunca activó dejaría stock de más.
            "sin_articulo_ids": f.sin_articulo_ids,
            "valores_variante_ids": f.valores_variante_ids,
        }
        for f in filas
    ]


def _borrar_hijos_primero(session: Session, filas: list[VentaItem]) -> None:
    """El FK rechaza borrar un padre que todavía tiene un hijo.

    El flush **entre medio** es lo que lo garantiza: ordenar el bucle no
    alcanza porque `delete()` solo marca, y el orden real de los DELETE lo
    decide SQLAlchemy al vaciar la sesión. Como `padre_venta_item_id` no
    tiene `relationship` declarada, no sabe que la FK es autorreferencial y
    ordena a su antojo — sin el flush esto pasaba en local y fallaba en CI,
    que es la peor forma de "funcionar".
    """
    hijos = [f for f in filas if f.padre_venta_item_id is not None]
    for fila in hijos:
        session.delete(fila)
    if hijos:
        session.flush()
    for fila in filas:
        if fila.padre_venta_item_id is None:
            session.delete(fila)
    session.flush()


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
    todas = VentaRepo(session).items(venta_id)
    filas = [f for f in todas if f.id in pedidos]
    if len(filas) != len(pedidos):
        raise NoEncontrado("alguna línea no pertenece a esta venta")

    filas = _con_sus_extras(filas, todas)
    devueltos = _a_reponer(session, filas)
    _borrar_hijos_primero(session, filas)

    restantes = VentaRepo(session).items(venta_id)
    # Quitar una pizza puede desactivar el 2x1 que esa pizza activaba: la
    # promoción desaparece sola en vez de quedar cobrada sobre lo que ya no
    # está (ADR-076).
    promociones.recalcular_promociones(session, venta)
    venta.total = total_a_cobrar(session, venta)
    # Sin líneas no queda orden que preparar: la venta se anula entera.
    if not restantes:
        venta.estado = "anulada"

    event_bus.publish(
        "sales.lineas_anuladas",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            # Los lee inventory para saber si además hay que reversar el
            # gasto de alimentación de personal (RN-COM-025). Quitar algunas
            # líneas NO lo reversa: el asiento es de la orden entera y
            # reversarlo por una línea borraría el gasto de las demás.
            "tipo": venta.tipo,
            "venta_anulada": venta.estado == "anulada",
            "autorizado_por": str(autorizado_por),
            "motivo": motivo,
            "items": devueltos,
        },
        session=session,
    )
    return venta


def _exigir_cuenta_sin_pagos(pago_repo: PagoRepo, venta_id: uuid.UUID, grupo: int) -> None:
    """Una cuenta con un pago confirmado ya no se traslada: eso es nota de
    crédito, no un traslado (RN-CPP-009)."""
    if sum(pago_repo.confirmados(venta_id, grupo), Decimal(0)) > 0:
        raise Conflicto(
            f"la cuenta {grupo} ya tiene pagos registrados: eso es nota de "
            "crédito, no un traslado"
        )


def _filas_a_mover(
    venta_repo: VentaRepo, venta_id: uuid.UUID, venta_item_ids: list[uuid.UUID]
) -> list[VentaItem]:
    """Las líneas pedidas, ya con sus extras arrastrados (RN-COM-021): la
    pizza no puede quedar en una cuenta y su sabor extra en otra."""
    pedidos = set(venta_item_ids)
    todas = venta_repo.items(venta_id)
    filas = [f for f in todas if f.id in pedidos]
    if len(filas) != len(pedidos):
        raise NoEncontrado("alguna línea no pertenece a esta venta")
    if any(f.padre_venta_item_id is not None for f in filas):
        raise ReglaNegocio(
            "un extra se mueve con su plato, no por separado (RN-COM-021)"
        )
    return _con_sus_extras(filas, todas)


def _resolver_destino_traslado(
    session: Session,
    origen: Venta,
    *,
    venta_id: uuid.UUID,
    destino_venta_id: uuid.UUID | None,
    destino_mesa_id: uuid.UUID | None,
    destino_comensales: int | None,
    grupo_cobro: int | None,
) -> tuple[Venta, int]:
    """A dónde van las líneas y con qué `grupo_cobro`, para los tres casos
    de RN-COM-043. Devuelve `(destino, nuevo_grupo)`; `destino is origen`
    cuando el traslado es separar la cuenta de la misma orden."""
    pago_repo = PagoRepo(session)
    if destino_mesa_id is not None:
        destino = _abrir_mesa_para_traslado(
            session, origen, mesa_id=destino_mesa_id, comensales=destino_comensales
        )
        return destino, rules.GRUPO_COBRO_UNICO

    if destino_venta_id is not None:
        if destino_venta_id == venta_id:
            raise ReglaNegocio(
                "para separar la cuenta de la misma orden no indiques "
                "destino_venta_id: manda grupo_cobro"
            )
        destino = VentaRepo(session).get(destino_venta_id)
        if destino is None:
            raise NoEncontrado("venta destino no encontrada")
        if destino.estado != "orden":
            raise Conflicto(f"la venta destino está {destino.estado}: no admite líneas")
        if destino.sucursal_id != origen.sucursal_id:
            raise ReglaNegocio("no se puede mover entre sucursales distintas")
        if destino.tipo != origen.tipo:
            raise ReglaNegocio("no se puede mezclar consumo de personal con una venta")
        nuevo_grupo = grupo_cobro or rules.GRUPO_COBRO_UNICO
        _exigir_cuenta_sin_pagos(pago_repo, destino_venta_id, nuevo_grupo)
        return destino, nuevo_grupo

    # Misma orden, otra cuenta: es "cobrar seleccionados" del PDV.
    if grupo_cobro is None:
        raise ReglaNegocio("indica destino_venta_id, destino_mesa_id o grupo_cobro")
    _exigir_cuenta_sin_pagos(pago_repo, venta_id, grupo_cobro)
    return origen, grupo_cobro


def _registrar_traslado(
    session: Session,
    *,
    origen: Venta,
    destino: Venta,
    filas: list[VentaItem],
    grupos_origen: list[int],
    nuevo_grupo: int,
    usuario_id: uuid.UUID,
) -> None:
    """Auditoría (una entrada por venta afectada) y `sales.lineas_movidas`.
    Sin evento de `inventory`: el insumo no se movió del almacén (ADR-071)."""
    monto = _subtotal(filas)
    movimiento_id = uuid.uuid4()
    afectadas = {origen, destino} if destino is not origen else {origen}
    for venta_afectada in afectadas:
        auditoria.registrar(
            session,
            usuario_id=usuario_id,
            entidad="venta",
            entidad_id=venta_afectada.id,
            accion="mover_lineas",
            datos_antes={"grupos_origen": grupos_origen},
            datos_despues={
                "movimiento_id": str(movimiento_id),
                "origen_venta_id": str(origen.id),
                "destino_venta_id": str(destino.id),
                "grupo_destino": nuevo_grupo,
                "lineas": len(filas),
                "monto": str(monto),
            },
            sucursal_id=venta_afectada.sucursal_id,
        )
    event_bus.publish(
        "sales.lineas_movidas",
        {
            "movimiento_id": str(movimiento_id),
            "origen_venta_id": str(origen.id),
            "destino_venta_id": str(destino.id),
            "sucursal_id": str(origen.sucursal_id),
            "grupos_origen": grupos_origen,
            "grupo_destino": nuevo_grupo,
            "monto": str(monto),
            "usuario_id": str(usuario_id),
            "items": [
                {"venta_item_id": str(f.id), "cantidad": str(f.cantidad)} for f in filas
            ],
        },
        session=session,
    )


def mover_lineas(
    session: Session,
    *,
    venta_id: uuid.UUID,
    venta_item_ids: list[uuid.UUID],
    usuario_id: uuid.UUID,
    destino_venta_id: uuid.UUID | None = None,
    destino_mesa_id: uuid.UUID | None = None,
    destino_comensales: int | None = None,
    grupo_cobro: int | None = None,
) -> tuple[Venta, Venta]:
    """Reasigna líneas de una orden YA enviada a otro destino (RN-COM-043):
    otra orden abierta, una mesa libre, o la misma orden con otra cuenta —
    que es como el PDV implementa "cobrar seleccionados" (RN-COM-018).

    Mover no es anular: el insumo ya salió del almacén cuando la línea se
    creó y el plato sigue existiendo, solo cambia de cuenta — a propósito
    **no** se publica ningún evento de `inventory`. Tampoco genera un
    asiento de reclasificación: origen y destino asientan contra las mismas
    cuentas (`regla_asiento` es una por empresa+evento), así que el efecto
    neto en el libro es cero; solo `referencia_origen` queda desalineado por
    venta, aceptado como deuda (ver ADR-071).

    A diferencia de `anular_lineas`, no exige PIN de supervisor: el producto
    sigue existiendo en alguna orden que se va a pagar o a anular, y anular
    sí pide firma. El rastro de quién movió qué queda en `audit_log` (dos
    veces, una por venta) y en `sales.lineas_movidas`.

    No preparado dos veces: `estado_preparacion` y `etapa_kds` viajan con la
    línea sin tocarse, así que KDS ve lo ya cocinado como ya cocinado en la
    orden destino.
    """
    if not venta_item_ids:
        raise ReglaNegocio("indica al menos una línea a mover")
    if destino_venta_id is not None and destino_mesa_id is not None:
        raise ReglaNegocio(
            "indica una sola orden destino: otra venta o una mesa, no ambas"
        )

    venta_repo = VentaRepo(session)
    origen = venta_repo.get(venta_id)
    if origen is None:
        raise NoEncontrado("venta no encontrada")
    if origen.estado != "orden":
        raise Conflicto(f"la venta está {origen.estado}: no admite mover líneas")

    filas = _filas_a_mover(venta_repo, venta_id, venta_item_ids)
    grupos_origen = sorted({f.grupo_cobro for f in filas})
    pago_repo = PagoRepo(session)
    for g in grupos_origen:
        _exigir_cuenta_sin_pagos(pago_repo, venta_id, g)

    destino, nuevo_grupo = _resolver_destino_traslado(
        session,
        origen,
        venta_id=venta_id,
        destino_venta_id=destino_venta_id,
        destino_mesa_id=destino_mesa_id,
        destino_comensales=destino_comensales,
        grupo_cobro=grupo_cobro,
    )

    # Al cambiar de orden, la línea entra a la cola del destino como una tanda
    # propia (ADR-075): la del origen numeraba los envíos de OTRO pedido y
    # chocaría con los de este. Una sola tanda para todo el lote — se movieron
    # juntas y en cocina son la misma comanda.
    tanda_destino = (
        venta_repo.siguiente_tanda(destino.id) if destino is not origen else None
    )
    for fila in filas:
        fila.venta_id = destino.id
        fila.grupo_cobro = nuevo_grupo
        if tanda_destino is not None:
            fila.tanda = tanda_destino
    session.flush()

    # Las dos órdenes cambiaron de contenido, así que las dos reevalúan: lo
    # que se fue puede haber roto una promoción del origen y armado una en el
    # destino (ADR-076).
    promociones.recalcular_promociones(session, origen)
    origen.total = total_a_cobrar(session, origen)
    if destino is not origen and not venta_repo.items(venta_id):
        # Sin líneas no queda orden que preparar ni mesa que ocupar.
        origen.estado = "anulada"
    if destino is not origen:
        promociones.recalcular_promociones(session, destino)
        destino.total = total_a_cobrar(session, destino)

    _registrar_traslado(
        session,
        origen=origen,
        destino=destino,
        filas=filas,
        grupos_origen=grupos_origen,
        nuevo_grupo=nuevo_grupo,
        usuario_id=usuario_id,
    )
    return origen, destino


def fijar_nota_cocina(
    session: Session, *, venta_id: uuid.UUID, nota: str | None
) -> Venta:
    """Cambia cómo se sirve el pedido. `None` la quita.

    Se puede con la orden ya en cocina porque así se pide de verdad: "las
    bebidas al final" se dice a mitad del servicio, no al tomar la comanda.
    Después del cobro no: la cuenta está cerrada y no hay nada que servir.

    Sin firma de nadie y sin evento: no toca el total, no mueve inventario y
    no cambia qué se prepara — solo en qué orden sale.
    """
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if venta.estado != "orden":
        raise Conflicto(f"la venta está {venta.estado}: ya no se está sirviendo")
    venta.nota_cocina = (nota or "").strip() or None
    return venta


def lineas_en_ventana(
    session: Session, venta_id: uuid.UUID, venta_item_ids: list[uuid.UUID]
) -> bool:
    """¿Todas esas líneas siguen dentro de la ventana de corrección?

    **Todas**, no alguna: si una sola ya salió de la ventana, el lote entero
    necesita firma. Al revés —dejar pasar el lote porque una es reciente— sería
    la forma de quitar cualquier línea vieja acompañándola de una nueva.
    """
    pedidos = set(venta_item_ids)
    filas = [f for f in VentaRepo(session).items(venta_id) if f.id in pedidos]
    return bool(filas) and all(rules.dentro_de_ventana(f.created_at) for f in filas)


def venta_en_ventana(session: Session, venta_id: uuid.UUID) -> bool:
    """¿La orden se envió hace menos de la ventana de corrección?

    Se mide contra la **última línea** y no contra la creación de la venta:
    una mesa que sigue pidiendo tiene la orden abierta desde hace una hora,
    pero lo último que mandó a cocina puede ser de hace un minuto — y es eso
    lo que todavía se puede deshacer sin molestar a nadie.
    """
    filas = VentaRepo(session).items(venta_id)
    return bool(filas) and rules.dentro_de_ventana(max(f.created_at for f in filas))


def agregar_lineas(
    session: Session,
    *,
    venta_id: uuid.UUID,
    items: list[dict],
    usuario_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> Venta:
    """Suma líneas a una orden **ya enviada a cocina** (RN-COM-029).

    Una mesa pide de a poco: la primera comanda sale, y diez minutos después
    piden otra bebida. Sin esto había que abrir una orden nueva para el mismo
    cliente, que después se cobra por separado y se le entrega en dos veces.

    No exige autorización de nadie: agregar es lo que el negocio quiere que
    pase. Lo que sí sigue exigiendo firma después de la ventana es **quitar**,
    porque eso repone inventario.

    Publica `sales.venta_confirmada` con **lo agregado**, no con la venta
    entera: `items` ya era el detalle de la operación y `total` pasa a serlo
    también, así que inventory descuenta solo lo nuevo y accounting asienta
    solo el incremento. Republicar el total completo lo asentaría dos veces.

    Todo lo de esta llamada entra al KDS como una **tanda propia** (ADR-075):
    una comanda nueva en la cola de cocina, con su propio reloj, en vez de
    colarse dentro de la pastilla del pedido original.
    """
    repo = VentaRepo(session)
    venta = repo.get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if venta.estado != "orden":
        raise Conflicto(
            f"la venta está {venta.estado}: no admite líneas nuevas. "
            "Después del cobro se abre otra orden."
        )
    if not items:
        raise ReglaNegocio("indica al menos una línea a agregar")
    # Reintento del mismo envío: la respuesta anterior se perdió, pero el
    # aumento ya entró. Devolver la venta tal como quedó es lo único que no
    # le manda a la cocina una segunda comanda idéntica (RN-COM-002).
    if idempotency_key and repo.tanda_ya_registrada(idempotency_key):
        return venta

    filas, extras_por_padre, detalle_evento = _armar_lineas(
        session,
        items,
        sucursal_id=venta.sucursal_id,
        canal=venta.canal,
        modalidad=venta.modalidad,
        dia=venta.fecha_orden,
        gratis=rules.es_consumo_personal(venta.tipo),
    )
    # Lo que había que cobrar antes de tocar la orden. La diferencia contra
    # el total de después es lo que esta operación confirma de verdad.
    total_antes = total_a_cobrar(session, venta)
    # La tanda es de la operación, no de la línea: todo lo que el trabajador
    # confirmó de un envío sale junto en la misma comanda. Se calcula antes de
    # insertar nada, para que el `max` no se lea a sí mismo.
    tanda = repo.siguiente_tanda(venta.id)
    for fila in filas:
        fila.venta_id = venta.id
        fila.tanda = tanda
        session.add(fila)
    # Una sola fila lleva la marca: lo idempotente es el envío, no la línea.
    if idempotency_key:
        filas[0].idempotency_key = idempotency_key
    session.flush()
    for fila, hijos in zip(filas, extras_por_padre, strict=True):
        for hijo in hijos:
            hijo.venta_id = venta.id
            hijo.padre_venta_item_id = fila.id
            hijo.tanda = tanda
            session.add(hijo)
    session.flush()

    # Las promociones se reevalúan antes del total: el aumento puede activar
    # una que el pedido no cumplía (la segunda pizza es la que acaba de
    # entrar) o dejar de cumplir ninguna (ADR-076).
    promociones.recalcular_promociones(session, venta)
    # El total se recalcula entero (incluye el descuento de orden prorrateado)
    # y no se le suma el incremento: sumar dejaría fuera el reprorrateo.
    venta.total = total_a_cobrar(session, venta)
    # Lo que se confirma en esta operación es **cuánto sube lo que hay que
    # cobrar**, no el precio de lista de lo que entró (ADR-043 §3, ADR-076).
    #
    # Con una promoción de por medio dejan de ser lo mismo: la segunda pizza
    # de un 2x1 entra por S/ 40 de lista y no le suma un sol al total. Sumar
    # la lista dejaría a contabilidad asentando S/ 40 que la caja nunca
    # cobró, y los libros dejarían de cuadrar con el turno.
    #
    # El delta puede ser **negativo** cuando el aumento activa una promoción
    # que baja el total más de lo que la línea suma —agregar una gaseosa que
    # dispara un "20 % desde S/ 50"—. Se publica tal cual: el asiento tiene
    # que seguir a la caja, y taparlo con un cero dejaría los libros por
    # encima de lo cobrado, que es el error que este cálculo viene a evitar.
    # A centavos: lo que viaja a contabilidad es plata, y `_subtotal` puede
    # traer cuatro decimales de multiplicar cantidad por precio.
    agregado = (venta.total - total_antes).quantize(Decimal("0.01"))
    auditoria.registrar(
        session,
        usuario_id=usuario_id,
        entidad="venta",
        entidad_id=venta.id,
        accion="agregar_lineas",
        datos_despues={"lineas": len(filas), "agregado": str(agregado)},
        sucursal_id=venta.sucursal_id,
    )
    _confirmar(
        session,
        venta,
        detalle_evento=detalle_evento,
        consumo=rules.es_consumo_personal(venta.tipo),
        registrado_por=usuario_id,
        total=agregado,
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
    estado_previo = venta.estado
    venta.estado = "anulada"
    auditoria.registrar(
        session,
        usuario_id=usuario_id,
        entidad="venta",
        entidad_id=venta.id,
        accion="anular",
        datos_antes={"estado": estado_previo, "total": str(venta.total)},
        datos_despues={"estado": "anulada"},
        sucursal_id=venta.sucursal_id,
    )
    productos = ProductoComercialRepo(session)
    items = []
    for it in VentaRepo(session).items(venta_id):
        prod = productos.get(it.producto_comercial_id)
        items.append(
            {
                "receta_id": str(prod.receta_id),
                "cantidad": str(it.cantidad),
                "sin_articulo_ids": it.sin_articulo_ids,
                "valores_variante_ids": it.valores_variante_ids,
            }
        )
    event_bus.publish(
        "sales.venta_anulada",
        {
            "venta_id": str(venta.id),
            "sucursal_id": str(venta.sucursal_id),
            "tipo": venta.tipo,
            "venta_anulada": True,
            "usuario_id": str(usuario_id),
            "items": items,
        },
        session=session,
    )
    return venta
