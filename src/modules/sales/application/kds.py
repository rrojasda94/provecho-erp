"""Casos de uso del KDS: pantallas configurables, cadena de estaciones,
cola, avance de ítems (bump), avance real del pedido y comanda imprimible.

El estado de preparación vive en `venta_item` — fuente única. Cada
pantalla es solo un FILTRO sobre ese estado, por eso el avance que
muestra cualquier pantalla siempre es el real. El frontend refresca por
polling; push (Redis/WebSocket) queda para el slice de tiempo real.

La cadena (armado → horno → despacho) es `kds_pantalla.orden` +
`venta_item.etapa_kds`, y se resuelve entera en `_estacion()`: la misma
función dice qué estación le toca a una línea y cuál es la siguiente
(ADR-044). Un solo lugar, porque cola y avance que discrepen dejarían
líneas invisibles en cocina.
"""

import textwrap
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application.queries_publicas import nombres_de_articulos
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.application.impresion import encabezado as encabezado_de
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    Atributo,
    AtributoValor,
    KdsPantalla,
    ProductoAtributoValor,
    ProductoComercial,
    Venta,
    VentaItem,
)
from src.shared import fechas, impresion

TIPOS_PANTALLA = {"preparacion", "despacho"}

# Estados de la venta que siguen teniendo algo que hacer en cocina.
#
# Incluye `facturada` y `cerrada` a propósito: lo que saca un pedido de la
# cola es haberlo ENTREGADO, no haberlo cobrado (ADR-078). Antes la cola
# miraba solo `orden` y `pagada`, y como `emitir_comprobante` pasa la venta a
# `facturada` en cuanto Factiliza responde —una tarea async, a segundos del
# cobro—, el pedido para llevar que se cobra de una sola vez podía
# desaparecer de la pantalla antes de que la cocina llegara a verlo. El
# historial ya usaba esta misma lista; la cola se había quedado corta.
ESTADOS_EN_COCINA = ("orden", "pagada", "facturada", "cerrada")


# --- Configuración de pantallas ----------------------------------------------
def crear_pantalla(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    nombre: str,
    tipo: str,
    categoria_ids: list[str] | None = None,
    orden: int = 0,
) -> KdsPantalla:
    if tipo not in TIPOS_PANTALLA:
        raise ReglaNegocio(f"tipo de pantalla inválido: {tipo}")
    _validar_orden(orden)
    existe = session.scalar(
        select(KdsPantalla).where(
            KdsPantalla.sucursal_id == sucursal_id,
            KdsPantalla.nombre == nombre,
            KdsPantalla.deleted_at.is_(None),
        )
    )
    if existe:
        raise Conflicto(f"pantalla '{nombre}' ya existe en la sucursal")
    pantalla = KdsPantalla(
        sucursal_id=sucursal_id, nombre=nombre, tipo=tipo,
        categoria_ids=categoria_ids, orden=orden,
    )
    session.add(pantalla)
    session.flush()
    return pantalla


def eliminar_pantalla(session: Session, pantalla_id: uuid.UUID) -> None:
    """Baja definitiva de una estación (`deleted_at`), no de un turno.

    `activo=False` ya existe y es la baja temporal — la pantalla se apaga y
    vuelve. Esto es lo otro: la estación deja de existir y su nombre queda
    libre para otra.

    Con la cola cargada no se borra: las líneas que están pasando por esa
    estación se quedarían sin dónde tacharse y el pedido se volvería
    invisible en cocina. Primero se vacía, después se borra.
    """
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None or pantalla.deleted_at is not None:
        raise NoEncontrado("pantalla no encontrada")
    if cola_pantalla(session, pantalla_id):
        raise Conflicto(
            "la pantalla tiene pedidos en cola: desactívala o termina la cola "
            "antes de borrarla"
        )
    pantalla.deleted_at = datetime.now(UTC)


def _validar_orden(orden: int) -> None:
    """La cadena se recorre hacia adelante y `etapa_kds` nace en 0: un orden
    negativo sería un eslabón al que nunca se llega."""
    if orden < 0:
        raise ReglaNegocio("el orden de la estación no puede ser negativo")


def editar_pantalla(session: Session, pantalla_id: uuid.UUID, **campos) -> KdsPantalla:
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None:
        raise NoEncontrado("pantalla no encontrada")
    destino = campos.get("sucursal_id")
    if destino is not None and destino != pantalla.sucursal_id:
        _mudar_de_sucursal(session, pantalla, destino)
    for campo in ("nombre", "tipo", "categoria_ids", "activo", "orden"):
        if campo in campos and campos[campo] is not None:
            if campo == "tipo" and campos[campo] not in TIPOS_PANTALLA:
                raise ReglaNegocio(f"tipo de pantalla inválido: {campos[campo]}")
            if campo == "orden":
                _validar_orden(campos[campo])
            setattr(pantalla, campo, campos[campo])
    return pantalla


def _mudar_de_sucursal(
    session: Session, pantalla: KdsPantalla, destino: uuid.UUID
) -> None:
    """Mover una estación a otra sucursal.

    Con la cola cargada, no: las líneas que están pasando por esta estación
    quedarían esperando en una cocina que ya no las mira, y el pedido se
    vuelve invisible sin que nadie se entere. Mismo criterio que borrarla
    —primero se vacía—.

    El nombre tiene que estar libre allá: el índice único es
    `(sucursal_id, nombre)` entre las vivas, y un IntegrityError crudo no le
    dice a nadie qué hacer.
    """
    if cola_pantalla(session, pantalla.id):
        raise Conflicto(
            "la pantalla tiene pedidos en cola: termina la cola antes de "
            "moverla de sucursal"
        )
    choca = session.scalar(
        select(KdsPantalla).where(
            KdsPantalla.sucursal_id == destino,
            KdsPantalla.nombre == pantalla.nombre,
            KdsPantalla.deleted_at.is_(None),
        )
    )
    if choca:
        raise Conflicto(
            f"la sucursal destino ya tiene una pantalla '{pantalla.nombre}'"
        )
    pantalla.sucursal_id = destino


def listar_pantallas(
    session: Session, sucursal_id: uuid.UUID | None = None
) -> list[KdsPantalla]:
    q = select(KdsPantalla).where(KdsPantalla.deleted_at.is_(None))
    if sucursal_id is not None:
        q = q.where(KdsPantalla.sucursal_id == sucursal_id)
    # Ordenadas por la cadena: la lista de estaciones ES el recorrido del
    # pedido, y mostrarla alfabética lo escondería.
    return list(session.scalars(q.order_by(KdsPantalla.orden, KdsPantalla.nombre)))


# --- Cola y avance ------------------------------------------------------------
def _items_de_venta(session: Session, venta_id: uuid.UUID) -> list[tuple]:
    """[(item, producto)] de una venta, extras incluidos."""
    return list(
        session.execute(
            select(VentaItem, ProductoComercial)
            .join(
                ProductoComercial,
                ProductoComercial.id == VentaItem.producto_comercial_id,
            )
            .where(VentaItem.venta_id == venta_id)
        )
    )


def _extras_de(pares: list[tuple]) -> dict[uuid.UUID, list[tuple]]:
    """`venta_item_id` del plato → los pares de sus extras.

    Un extra es fila propia (`padre_venta_item_id`) porque tiene su receta,
    su precio y se anula solo. Pero en cocina **no es un plato aparte**: el
    sabor de una pizza no se prepara en otra estación ni se tacha por su
    cuenta (RN-CUP-014). Acá se agrupan para que la tarjeta muestre uno y no
    dos — mismo criterio que `ventas.listar_items` usa para el ticket.
    """
    hijos: dict[uuid.UUID, list[tuple]] = {}
    for item, prod in pares:
        if item.padre_venta_item_id is not None:
            hijos.setdefault(item.padre_venta_item_id, []).append((item, prod))
    return hijos


def _tandas_de(pares: list[tuple]) -> list[tuple[int, list[tuple]]]:
    """Los envíos a cocina de una venta, en orden (ADR-075).

    Una mesa que pide de a poco es UNA venta, pero para la cocina cada envío
    es una comanda distinta: sin separarlas, el postre pedido a las 21:40
    aparecía en la misma pastilla que la entrada de las 20:15 y no había
    forma de ver qué acababa de entrar.

    La tanda la manda **el plato**, no cada fila: un extra se prepara con lo
    suyo (RN-CUP-014), así que se agrupa por la tanda de su padre aunque la
    propia diga otra cosa. Sin ese cuidado, un dato viejo con las dos
    descoordinadas dejaría al extra en un grupo donde su plato no está — y
    como la tarjeta se arma recorriendo platos, desaparecería de la pantalla.
    """
    del_plato = {it.id: it.tanda for it, _ in pares if it.padre_venta_item_id is None}
    grupos: dict[int, list[tuple]] = {}
    for item, producto in pares:
        clave = del_plato.get(item.padre_venta_item_id or item.id, item.tanda)
        grupos.setdefault(clave, []).append((item, producto))
    return sorted(grupos.items())


def _familia(pares: list[tuple], item: VentaItem) -> list[VentaItem]:
    """El plato y sus extras: lo que cocina trata como una sola cosa."""
    padre_id = item.padre_venta_item_id or item.id
    return [it for it, _ in pares if it.id == padre_id or it.padre_venta_item_id == padre_id]


def _restas_por_item(session: Session, pares: list[tuple]) -> dict[uuid.UUID, list[str]]:
    """`venta_item_id` → ["Cebolla", "Aceituna"]: lo que el plato NO lleva.

    Cocina necesita el nombre, no el id. `sales` guarda ids de artículo y no
    puede leer `articulo`, así que los nombres salen del contrato público de
    `inventory`. Un artículo borrado deja "—": el pedido igual tiene que
    poder imprimirse.

    ponytail: una consulta por venta (la cola las recorre en bucle). Con una
    cola de decenas de pedidos no se nota; si el KDS crece a cientos, esto
    se agrupa en una sola consulta por cola.
    """
    ids = {
        uuid.UUID(a) for it, _ in pares for a in (it.sin_articulo_ids or [])
    }
    if not ids:
        return {}
    nombres = nombres_de_articulos(session, ids)
    return {
        it.id: [nombres.get(uuid.UUID(a), "—") for a in it.sin_articulo_ids]
        for it, _ in pares
        if it.sin_articulo_ids
    }


def _valores_por_item(session: Session, pares: list[tuple]) -> dict[uuid.UUID, list[str]]:
    """`venta_item_id` → ["Mitad 1: Americana", "Mitad 2: Hawaiana"].

    Espejo de `_restas_por_item` y por el mismo motivo: cocina necesita
    nombres, no ids. Antes el sabor era un extra y salía impreso solo; desde
    que vive en `producto_atributo_valor` la comanda de una MitadXMitad
    dejaría de decir **qué mitades es**, que es justo lo único que el
    pizzero necesita saber de ese plato.

    El atributo va delante del valor porque "Americana" a secas no dice de
    qué mitad es, y en una mitad-y-mitad esa es toda la información.
    """
    ids = {
        uuid.UUID(str(v)) for it, _ in pares for v in (it.valores_variante_ids or [])
    }
    if not ids:
        return {}
    filas = session.execute(
        select(ProductoAtributoValor.id, Atributo.nombre, AtributoValor.nombre)
        .join(AtributoValor, ProductoAtributoValor.atributo_valor_id == AtributoValor.id)
        .join(Atributo, AtributoValor.atributo_id == Atributo.id)
        .where(ProductoAtributoValor.id.in_(ids))
    )
    etiqueta = {ptav: f"{atributo}: {valor}" for ptav, atributo, valor in filas}
    return {
        it.id: [
            etiqueta.get(uuid.UUID(str(v)), "—") for v in it.valores_variante_ids
        ]
        for it, _ in pares
        if it.valores_variante_ids
    }


def _pertenece(pantalla: KdsPantalla, producto: ProductoComercial) -> bool:
    """¿La pantalla atiende la categoría de este producto? NULL/[] = todas."""
    if not pantalla.categoria_ids:
        return True
    return str(producto.categoria_id) in pantalla.categoria_ids


def _cadena(session: Session, sucursal_id: uuid.UUID) -> list[KdsPantalla]:
    """Estaciones de preparación activas de la sucursal, en orden de recorrido.

    Despacho queda fuera a propósito: no es un eslabón que la línea tenga
    que atravesar, es lo que mira el pedido cuando ya no le queda ninguno.
    """
    return list(
        session.scalars(
            select(KdsPantalla)
            .where(
                KdsPantalla.sucursal_id == sucursal_id,
                KdsPantalla.tipo == "preparacion",
                KdsPantalla.activo.is_(True),
                KdsPantalla.deleted_at.is_(None),
            )
            .order_by(KdsPantalla.orden, KdsPantalla.nombre)
        )
    )


def _estacion(
    cadena: list[KdsPantalla], producto: ProductoComercial, desde: int
) -> KdsPantalla | None:
    """Primera estación con `orden >= desde` que atiende este producto.

    Es `>=` y no `==` a propósito: si el eslabón exacto de la línea ya no
    existe —lo desactivaron, le cambiaron las categorías—, la línea cae a
    la siguiente estación que sí la acepte en vez de quedar invisible.
    `None` = ya no queda cadena por delante: la línea está lista.

    Y si NINGUNA estación declara la categoría —el producto no tiene
    `categoria_id`, o su categoría no está en ningún `categoria_ids`— la
    atiende la primera de la cadena. Es la misma tolerancia llevada hasta el
    final: antes esa línea no aparecía en ninguna pantalla, se quedaba
    `pendiente` para siempre y dejaba el pedido sin poder entregarse nunca,
    sin que nadie en el local pudiera enterarse. Una comanda mal ruteada se
    arregla mirando la tarjeta; una comanda invisible, no.

    El descarte se mide sobre la cadena entera y no desde `desde`, para que
    una huérfana ya bumpeada siga terminando en `None` (= lista) en vez de
    volver a caer en la primera estación y quedar girando.
    """
    for pantalla in cadena:
        if pantalla.orden >= desde and _pertenece(pantalla, producto):
            return pantalla
    if cadena and desde <= cadena[0].orden:
        if not any(_pertenece(p, producto) for p in cadena):
            return cadena[0]
    return None


def _estacion_de(
    cadena: list[KdsPantalla], item: VentaItem, producto: ProductoComercial
) -> KdsPantalla | None:
    """Estación que le toca AHORA a la línea. `None` = ya terminó cocina."""
    if item.estado_preparacion in ("listo", "entregado"):
        return None
    return _estacion(cadena, producto, item.etapa_kds)


def _item_a_dict(
    item: VentaItem,
    producto: ProductoComercial,
    restas: dict[uuid.UUID, list[str]],
    estacion: KdsPantalla | None,
    extras: list[tuple] = (),
    valores: dict[uuid.UUID, list[str]] | None = None,
) -> dict:
    return {
        "venta_item_id": str(item.id),
        "producto": producto.nombre,
        "cantidad": str(item.cantidad),
        "estado": item.estado_preparacion,
        "sin": restas.get(item.id, []),
        # QUÉ es el plato: las dos mitades de una MitadXMitad. Distinto de
        # `extras`, que es lo que se le agrega — acá no hay línea cobrada, la
        # elección cambia la receta que se prepara (ADR-056).
        "valores": (valores or {}).get(item.id, []),
        # Lo que el plato lleva ADEMÁS: el sabor de la pizza, el queso extra.
        # Van acá dentro y no como líneas sueltas porque son el mismo plato
        # (RN-CUP-014) — sueltas, la tarjeta decía "1 Pizza Personal" y
        # "1 Peperoni" y el cocinero leía dos cosas donde hay una.
        "extras": [
            {"producto": prod.nombre, "cantidad": str(hijo.cantidad)}
            for hijo, prod in extras
        ],
        "etapa_kds": item.etapa_kds,
        # Lo que el mesero le dijo a cocina sobre este plato. Va con la línea
        # y no al pie: es de este plato, y al pie se leería como si aplicara
        # a todo el pedido — que es lo que sí hace `nota_cocina`.
        "nota": item.nota,
        # Dónde está la línea ahora mismo. Es lo que despacho necesita para
        # saber si el pedido espera por el horno o por la barra; `None` = ya
        # no espera por nadie.
        "estacion": estacion.nombre if estacion else None,
    }


def cola_pantalla(session: Session, pantalla_id: uuid.UUID) -> list[dict]:
    """Pedidos activos de la sucursal, con los ítems que competen a la
    pantalla y el avance REAL del pedido completo (todas las categorías).

    **Preparación ve una tarjeta por tanda** y despacho una por pedido
    (ADR-075). No es una inconsistencia: la cocina prepara lo que acaba de
    entrar y necesita ver cada envío con su propio reloj, mientras que el
    despacho arma la bolsa contra el pedido completo (ADR-044) y partirlo en
    dos tarjetas sería la forma de entregar media orden.
    """
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None or pantalla.deleted_at is not None:
        raise NoEncontrado("pantalla no encontrada")
    cadena = _cadena(session, pantalla.sucursal_id)

    ventas = session.scalars(
        select(Venta)
        .where(
            Venta.sucursal_id == pantalla.sucursal_id,
            Venta.estado.in_(ESTADOS_EN_COCINA),
        )
        .order_by(Venta.fecha_orden, Venta.numero_orden)
    )

    cola = []
    for venta in ventas:
        pares = _items_de_venta(session, venta.id)
        estados_todos = [it.estado_preparacion for it, _ in pares]
        # Pedido cerrado en cocina: nada que mostrar.
        if estados_todos and all(e == "entregado" for e in estados_todos):
            continue
        restas = _restas_por_item(session, pares)
        valores = _valores_por_item(session, pares)
        grupos = (
            _tandas_de(pares) if pantalla.tipo == "preparacion" else [(1, pares)]
        )
        for tanda, del_grupo in grupos:
            estados = [it.estado_preparacion for it, _ in del_grupo]
            mios, pendiente_aqui = _items_de_pantalla(
                pantalla, cadena, del_grupo, restas, valores
            )
            if pantalla.tipo == "preparacion":
                # La estación ve TODOS sus ítems, incluidos los que ya tachó:
                # el ítem tachado tiene que seguir a la vista de quien lo
                # tachó. La tanda desaparece de esta cola recién cuando la
                # estación terminó todo lo suyo — no ítem por ítem.
                if not mios or not pendiente_aqui:
                    continue
            elif not any(e == "listo" for e in estados_todos):
                # Despacho: muestra pedidos con algo listo o todo listo.
                continue
            cola.append(
                {
                    "venta_id": str(venta.id),
                    "numero_orden": venta.numero_orden,
                    # Qué envío del pedido es esta tarjeta. Despacho siempre
                    # manda 1: su unidad es el pedido entero.
                    "tanda": tanda,
                    "referencia_atencion": venta.referencia_atencion,
                    # Despacho arma la bolsa mirando esta pantalla: la
                    # dirección va acá y no solo en el papel.
                    "direccion_entrega": venta.direccion_entrega,
                    "modalidad": venta.modalidad,
                    "canal": venta.canal,
                    # La cocina tiene que saber que está preparando comida del
                    # personal: cambia la prioridad frente a un pedido de
                    # cliente.
                    "tipo": venta.tipo,
                    "consumo_motivo": venta.consumo_motivo,
                    # Cómo se sirve el pedido entero. Va en TODAS las tandas:
                    # "servir todo junto" es una instrucción del pedido, y la
                    # tanda que no la lleve la ignoraría sin saberlo.
                    "nota_cocina": venta.nota_cocina,
                    "estado_pedido": rules.estado_pedido(estados),
                    # Desde cuándo espera. Sin esto la pantalla no puede saber
                    # si un pedido lleva cuatro minutos o cuarenta, y los dos
                    # se ven exactamente igual.
                    #
                    # Para la cocina es la hora de ESTA tanda, no la del
                    # pedido: una mesa abierta hace dos horas que acaba de
                    # pedir un café saldría en rojo, y el semáforo dejaría de
                    # significar algo el día que alguien se siente a comer sin
                    # apuro. Despacho sigue contando desde el pedido, que es
                    # lo que el cliente está esperando.
                    "creado_en": (
                        min(it.created_at for it, _ in del_grupo)
                        if pantalla.tipo == "preparacion"
                        else venta.created_at
                    ),
                    "items": mios,
                }
            )
    return cola


# El historial es para desatascar un error de hace un rato —«¿este pedido
# salió?»— y no para auditar la semana: eso lo responde el módulo de
# reportes, con sus filtros y sus permisos. Por eso se cuenta en días de
# negocio y arranca en el de hoy.
DIAS_HISTORIAL = 1
TOPE_HISTORIAL = 200


def historial_pantalla(
    session: Session, pantalla_id: uuid.UUID, dias: int = DIAS_HISTORIAL
) -> list[dict]:
    """Lo contrario de `cola_pantalla`: los pedidos que YA se entregaron.

    La cola los descarta en cuanto se cierran, y hasta ahora eso era todo lo
    que la cocina podía ver: un pedido entregado por error desaparecía de la
    pantalla sin dejar rastro y no había dónde ir a buscarlo. Acá están, con
    la hora en que se cerraron y —si hace falta— el botón para deshacerlo.

    La hora sale de `venta_item.updated_at` y no de una columna propia: el
    último cambio de un ítem entregado **es** su entrega. Una columna nueva
    para mostrar una hora en una pantalla de cocina no se paga sola.
    """
    pantalla = session.get(KdsPantalla, pantalla_id)
    if pantalla is None or pantalla.deleted_at is not None:
        raise NoEncontrado("pantalla no encontrada")
    cadena = _cadena(session, pantalla.sucursal_id)
    # `fecha_orden` es una fecha de calendario del negocio, no un instante:
    # se compara contra `fechas.hoy()` y no contra el reloj del servidor, que
    # en UTC ya está en el día siguiente desde las 19:00 hora Perú.
    desde = fechas.hoy() - timedelta(days=dias - 1)

    ventas = session.scalars(
        select(Venta)
        .where(
            Venta.sucursal_id == pantalla.sucursal_id,
            # `anulada` no: un pedido anulado no se entregó, se canceló.
            Venta.estado.in_(ESTADOS_EN_COCINA),
            Venta.fecha_orden >= desde,
        )
        .order_by(Venta.fecha_orden.desc(), Venta.numero_orden.desc())
    )

    historial = []
    for venta in ventas:
        pares = _items_de_venta(session, venta.id)
        estados_todos = [it.estado_preparacion for it, _ in pares]
        if not rules.pedido_entregado(estados_todos):
            continue
        restas = _restas_por_item(session, pares)
        valores = _valores_por_item(session, pares)
        mios, _ = _items_de_pantalla(pantalla, cadena, pares, restas, valores)
        # Una estación de preparación solo ve lo que pasó por ella; despacho
        # ve el pedido entero, igual que en la cola.
        if pantalla.tipo == "preparacion" and not mios:
            continue
        historial.append(
            {
                "venta_id": str(venta.id),
                "numero_orden": venta.numero_orden,
                "referencia_atencion": venta.referencia_atencion,
                "direccion_entrega": venta.direccion_entrega,
                "modalidad": venta.modalidad,
                "canal": venta.canal,
                "tipo": venta.tipo,
                "consumo_motivo": venta.consumo_motivo,
                "nota_cocina": venta.nota_cocina,
                "estado_pedido": "entregado",
                "creado_en": venta.created_at,
                "entregado_en": max(it.updated_at for it, _ in pares),
                "items": mios,
            }
        )
        if len(historial) >= TOPE_HISTORIAL:
            break
    return historial


def _items_de_pantalla(
    pantalla: KdsPantalla,
    cadena: list[KdsPantalla],
    pares: list[tuple],
    restas: dict[uuid.UUID, list[str]],
    valores: dict[uuid.UUID, list[str]] | None = None,
) -> tuple[list[dict], bool]:
    """Ítems que le competen a la pantalla, y si le queda algo por hacer.

    Recorre **solo los platos** (`padre_venta_item_id is None`): los extras
    viajan dentro del suyo, y su categoría no rutea nada (RN-CUP-014). Eso
    además cierra un agujero: un extra sin `categoria_id` no lo atendía
    ninguna estación filtrada, así que se quedaba `pendiente` para siempre y
    el pedido nunca llegaba a entregable.

    Una estación ve todos los de sus categorías, incluidos los que ya mandó
    al eslabón siguiente: el ítem tachado tiene que seguir a la vista de
    quien lo tachó, y `estacion` dice a dónde se fue. Lo que saca al pedido
    de esta cola no es que la línea avance, es que a la estación no le
    quede nada pendiente. Despacho ve el pedido completo.
    """
    hijos = _extras_de(pares)
    platos = [(it, prod) for it, prod in pares if it.padre_venta_item_id is None]
    if pantalla.tipo != "preparacion":
        return (
            [
                _item_a_dict(
                    it, prod, restas, _estacion_de(cadena, it, prod),
                    hijos.get(it.id, []), valores,
                )
                for it, prod in platos
            ],
            True,
        )
    mios, pendiente = [], False
    for it, prod in platos:
        estacion = _estacion_de(cadena, it, prod)
        # Es de esta pantalla si declara su categoría, o si la línea cayó acá
        # por no tener quién la declare. Sin la segunda mitad, la huérfana se
        # descartaba antes de que nadie llegara a preguntarle su estación:
        # `_estacion` podía adoptarla, pero este filtro ya la había tirado.
        if not _pertenece(pantalla, prod) and (
            estacion is None or estacion.id != pantalla.id
        ):
            continue
        if estacion is not None and estacion.orden == pantalla.orden:
            pendiente = True
        mios.append(
            _item_a_dict(
                it, prod, restas, estacion, hijos.get(it.id, []), valores,
            )
        )
    return mios, pendiente


def _linea_operable(
    session: Session, venta_item_id: uuid.UUID
) -> tuple[VentaItem, list[VentaItem], Venta, list[tuple]]:
    """El plato sobre el que se opera, su familia y su venta.

    Si llega el id de un extra se opera sobre su plato: en cocina el extra no
    existe por su cuenta (RN-CUP-014), así que rechazarlo sería un error sin
    salida para un cliente que todavía mande la línea suelta. El extra
    acompaña al plato en todo —si se quedara atrás, `estado_pedido` y
    `pedido_entregable`, que suman TODOS los ítems, dejarían el pedido sin
    poder entregarse nunca—.
    """
    pedido = session.get(VentaItem, venta_item_id)
    if pedido is None:
        raise NoEncontrado("ítem de venta no encontrado")
    venta = session.get(Venta, pedido.venta_id)
    if venta.estado == "anulada":
        raise Conflicto("la venta está anulada")
    pares = _items_de_venta(session, pedido.venta_id)
    familia = _familia(pares, pedido)
    item = next(it for it in familia if it.padre_venta_item_id is None)
    return item, familia, venta, pares


def avanzar_item(
    session: Session, venta_item_id: uuid.UUID, nuevo_estado: str
) -> VentaItem:
    if nuevo_estado == "entregado":
        # La entrega cierra el pedido completo y exige su propio permiso
        # (RN-CUP-005/006) — no se marca ítem por ítem desde cocina.
        raise ReglaNegocio(
            "la entrega se registra en POST /sales/ventas/{venta_id}/entrega"
        )
    item, familia, venta, pares = _linea_operable(session, venta_item_id)

    if not rules.transicion_preparacion_valida(item.estado_preparacion, nuevo_estado):
        raise ReglaNegocio(
            f"transición inválida: {item.estado_preparacion} → {nuevo_estado}"
        )
    if nuevo_estado == "listo" and _pasar_a_la_siguiente(session, item, venta):
        # Tachar en una estación intermedia no es "listo": es "listo ACÁ".
        # La línea sigue en preparación, ahora en el eslabón siguiente.
        for hijo in familia:
            hijo.etapa_kds = item.etapa_kds
        return item
    for hijo in familia:
        hijo.estado_preparacion = nuevo_estado

    estados = [it.estado_preparacion for it, _ in pares]
    if all(e in ("listo", "entregado") for e in estados):
        event_bus.publish(
            "sales.pedido_listo",
            {"venta_id": str(item.venta_id)},
            session=session,
        )
    return item


def retroceder_item(session: Session, venta_item_id: uuid.UUID) -> VentaItem:
    """Deshace **un** paso del avance de una línea (RN-CUP-002, 2026-08-26).

    Existe porque el avance se hace tocando una pantalla con las manos
    ocupadas y el toque equivocado no tenía vuelta: una línea mandada a la
    estación siguiente por error se quedaba allá, y en despacho un pedido
    marcado antes de tiempo no se podía devolver a la cocina.

    Deshace exactamente lo que hizo el toque anterior, que no siempre es lo
    mismo. El avance tiene dos ejes —`estado_preparacion` y `etapa_kds`— y
    tacharla en una estación intermedia mueve el segundo sin tocar el
    primero (ADR-044). Así que:

    1. `listo` vuelve a `en_preparacion`, en la misma estación.
    2. Si la línea fue empujada a un eslabón posterior, vuelve al anterior.
    3. `en_preparacion` en la primera estación vuelve a `pendiente`.

    `entregado` no se deshace acá: la entrega es un acto de la venta
    completa, con su propio permiso, y se deshace en
    `POST /sales/ventas/{venta_id}/deshacer-entrega`.
    """
    item, familia, venta, _ = _linea_operable(session, venta_item_id)
    if item.estado_preparacion == "entregado":
        raise ReglaNegocio(
            "el pedido ya se entregó: usa "
            "POST /sales/ventas/{venta_id}/deshacer-entrega"
        )
    if item.estado_preparacion == "listo":
        for hijo in familia:
            hijo.estado_preparacion = "en_preparacion"
        return item

    anterior = _estacion_anterior(session, item, venta)
    if anterior is not None:
        for hijo in familia:
            hijo.etapa_kds = anterior.orden
        return item

    previo = rules.paso_anterior(item.estado_preparacion)
    if previo is None:
        raise Conflicto("la línea no tiene ningún avance que deshacer")
    for hijo in familia:
        hijo.estado_preparacion = previo
    return item


def _estacion_anterior(
    session: Session, item: VentaItem, venta: Venta
) -> KdsPantalla | None:
    """El eslabón previo de ESTA línea, o `None` si está en el primero.

    Se busca entre las estaciones que atienden su categoría, no entre todas:
    una bebida que se saltó el horno sola tiene que volver a la barra, no al
    horno por el que nunca pasó.
    """
    producto = session.get(ProductoComercial, item.producto_comercial_id)
    cadena = _cadena(session, venta.sucursal_id)
    actual = _estacion(cadena, producto, item.etapa_kds)
    suyas = [p for p in cadena if _pertenece(p, producto)]
    if actual is None:
        # Sin estación por delante la línea ya salió de cocina: su último
        # eslabón es el final de su cadena.
        return suyas[-1] if suyas else None
    previas = [p for p in suyas if p.orden < actual.orden]
    return previas[-1] if previas else None


def _pasar_a_la_siguiente(session: Session, item: VentaItem, venta: Venta) -> bool:
    """Manda la línea al eslabón siguiente. `False` = no quedaba ninguno.

    El siguiente se busca desde la estación que la línea tiene AHORA y no
    desde `etapa_kds + 1`: si el eslabón exacto ya no existe, `etapa_kds`
    apunta más atrás que la estación real y sumarle uno devolvería la misma
    estación — la línea se quedaría rebotando ahí para siempre.
    """
    producto = session.get(ProductoComercial, item.producto_comercial_id)
    cadena = _cadena(session, venta.sucursal_id)
    actual = _estacion(cadena, producto, item.etapa_kds)
    if actual is None:
        return False
    siguiente = _estacion(cadena, producto, actual.orden + 1)
    if siguiente is None:
        return False
    item.etapa_kds = siguiente.orden
    return True


def avance_venta(session: Session, venta_id: uuid.UUID) -> dict:
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    pares = _items_de_venta(session, venta_id)
    estados = [it.estado_preparacion for it, _ in pares]
    restas = _restas_por_item(session, pares)
    valores = _valores_por_item(session, pares)
    cadena = _cadena(session, venta.sucursal_id)
    hijos = _extras_de(pares)
    return {
        "venta_id": str(venta_id),
        "numero_orden": venta.numero_orden,
        "referencia_atencion": venta.referencia_atencion,
        "estado_pedido": rules.estado_pedido(estados),
        "items": [
            _item_a_dict(
                it, prod, restas, _estacion_de(cadena, it, prod),
                hijos.get(it.id, []), valores,
            )
            for it, prod in pares
            if it.padre_venta_item_id is None
        ],
    }


# --- Comanda ------------------------------------------------------------------
# El ancho lo pone el papel, y todas las ticketeras del grupo son de 80 mm
# (ADR-067). Antes eran 32 columnas —58 mm— y la misma comanda salía con un
# tercio del rollo en blanco y los nombres largos cortados sin necesidad.
ANCHO_COMANDA = impresion.ANCHO


def _platos_en_papel(session: Session, pares: list[tuple]) -> list[str]:
    """Los platos de la comanda, cada uno con lo que lo define y lo modifica.

    Todo sangrado y en mayúsculas: en la cocina el papel se lee de reojo, y
    un extra o una resta que pasan desapercibidos salen como plato rehecho.
    """
    restas = _restas_por_item(session, pares)
    valores = _valores_por_item(session, pares)
    hijos = _extras_de(pares)
    lineas: list[str] = []
    for it, prod in pares:
        # El extra se imprime DENTRO de su plato, no como línea de primer
        # nivel: en el papel, "1x Pizza Personal" seguido de "1x Peperoni"
        # se lee como dos pizzas (RN-CUP-014).
        if it.padre_venta_item_id is not None:
            continue
        cant = f"{it.cantidad.normalize()}x"
        lineas.append(f"{cant} {prod.nombre}"[:ANCHO_COMANDA])
        # Los valores van primero porque dicen QUÉ es el plato —qué mitades
        # lleva la pizza—, mientras que extras y restas lo modifican.
        for etiqueta in valores.get(it.id, []):
            lineas.append(f"   > {etiqueta.upper()}"[:ANCHO_COMANDA])
        for hijo, extra in hijos.get(it.id, []):
            suf = "" if hijo.cantidad == 1 else f"{hijo.cantidad.normalize()}x "
            lineas.append(f"   + {suf}{extra.nombre.upper()}"[:ANCHO_COMANDA])
        for nombre in restas.get(it.id, []):
            lineas.append(f"   SIN {nombre.upper()}"[:ANCHO_COMANDA])
        # La nota va al final del plato, después de lo estructurado: es lo
        # que ninguna resta ni ningún atributo pudo expresar, y el cocinero
        # ya sabe de qué plato habla.
        if it.nota:
            lineas += [
                f"   ** {parte}"
                for parte in textwrap.wrap(it.nota.upper(), ANCHO_COMANDA - 6)
            ]
    return lineas


def comanda(session: Session, venta_id: uuid.UUID) -> dict:
    """Texto plano listo para impresora térmica. Incrementa el contador —
    más de una impresión = reimpresión (auditable)."""
    venta = session.get(Venta, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    pares = _items_de_venta(session, venta_id)

    venta.comanda_impresa_veces += 1
    reimpresion = venta.comanda_impresa_veces > 1

    lineas = [
        "*" * ANCHO_COMANDA,
        f"ORDEN #{venta.numero_orden}".center(ANCHO_COMANDA),
    ]
    if venta.referencia_atencion:
        lineas.append(venta.referencia_atencion.upper().center(ANCHO_COMANDA))
    lineas += [
        f"{venta.modalidad.upper()} / {venta.canal.upper()}".center(ANCHO_COMANDA),
        f"{venta.created_at:%d/%m/%Y %H:%M}".center(ANCHO_COMANDA),
        "*" * ANCHO_COMANDA,
    ]
    # La dirección se imprime en la comanda porque el papel es lo que sale
    # con el repartidor: si solo vive en la pantalla, alguien la copia a
    # mano y la copia es la que se equivoca.
    if venta.direccion_entrega:
        lineas.append("ENTREGAR EN:")
        lineas += textwrap.wrap(venta.direccion_entrega, ANCHO_COMANDA)
        lineas.append("-" * ANCHO_COMANDA)
    if rules.es_consumo_personal(venta.tipo):
        lineas.append("** CONSUMO PERSONAL **".center(ANCHO_COMANDA))
        lineas.append(f"({venta.consumo_motivo})".center(ANCHO_COMANDA))
        lineas.append("-" * ANCHO_COMANDA)
    if reimpresion:
        lineas.append("** REIMPRESION **".center(ANCHO_COMANDA))
        lineas.append("-" * ANCHO_COMANDA)
    lineas += _platos_en_papel(session, pares)
    # Al pie y no arriba: primero se lee qué hay que preparar, y después cómo
    # sale. Arriba competiría con el número de orden, que es lo que la cocina
    # busca de un vistazo.
    if venta.nota_cocina:
        lineas.append("-" * ANCHO_COMANDA)
        lineas.append("AL SERVIR:")
        lineas += textwrap.wrap(venta.nota_cocina.upper(), ANCHO_COMANDA)
    lineas.append("*" * ANCHO_COMANDA)
    return {
        "venta_id": str(venta_id),
        "numero_orden": venta.numero_orden,
        "reimpresion": reimpresion,
        "impresa_veces": venta.comanda_impresa_veces,
        # La cocina de un local multimarca imprime en el mismo rollo lo de
        # todas: sin membrete, de qué marca es el pedido se deduce leyendo
        # los platos.
        "encabezado": encabezado_de(session, venta.sucursal_id),
        "texto": "\n".join(lineas),
    }
