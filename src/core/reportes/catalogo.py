"""Catálogo de reportes: la lista cerrada de lo que se puede consultar.

**Decisión central (ADR-024): no hay constructor de consultas.** El cliente
manda un `codigo` del catálogo y filtros tipados; nunca una tabla, una
columna, un `order by` ni nada que termine dentro de un SQL. Un armador de
consultas genérico sobre el ERP entero sería a la vez la superficie de
inyección más grande del sistema y una fuga de RBAC (quien puede consultar
cualquier tabla puede leer sueldos desde el reporte de ventas).

Cada reporte declara el permiso **de su módulo dueño**, no uno propio de
reportes: así un `comprador` ve los reportes de compras y no los de ventas
sin que haya que mantener una segunda matriz de permisos en paralelo.

Agregar un reporte = una entrada acá. La función que lo resuelve tiene que
ser un contrato público (`application/queries_publicas.py`) del módulo
dueño: este archivo compone, no consulta.
"""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from src.modules.accounting.application import queries_publicas as accounting_q
from src.modules.inventory.application import queries_publicas as inventory_q
from src.modules.purchases.application import queries_publicas as purchases_q
from src.modules.rrhh.application import queries_publicas as rrhh_q
from src.modules.sales.application import queries_publicas as sales_q

# Cómo formatear la columna en la tabla y el gráfico. El backend no formatea
# (el `Decimal` viaja como string exacto), pero sí dice qué es cada cosa —
# el frontend no tiene por qué adivinar que "total" es dinero.
TIPOS_COLUMNA = ("texto", "numero", "dinero", "cantidad", "fecha", "id")

VISUALES = ("tabla", "barras", "lineas")


@dataclass(frozen=True)
class Columna:
    clave: str
    titulo: str
    tipo: str = "texto"
    # Si esta columna es el id de una entidad, a qué tipo de `src.core.destinos`
    # apunta. Una columna `tipo="id"` no se dibuja como celda: es el ancla del
    # enlace de la fila (ADR-036). Declararla como `Columna` y no como campo
    # aparte la hace pasar por el mismo whitelist de `ejecutar()`, sin
    # excepciones que después haya que recordar.
    enlace: str = ""


@dataclass(frozen=True)
class Reporte:
    codigo: str
    nombre: str
    descripcion: str
    permiso: str
    columnas: tuple[Columna, ...]
    consulta: Callable[..., list[dict]]
    # Visualización por defecto; cada tarjeta del tablero puede cambiarla.
    visual: str = "tabla"
    # Qué columna es la etiqueta y cuál el valor cuando se dibuja como
    # gráfico. Sin esto, un gráfico tendría que adivinar cuál de tres
    # columnas numéricas graficar.
    etiqueta: str = ""
    valor: str = ""
    # Si `False`, el filtro de sucursales del tablero no aplica y el
    # frontend lo dice en la tarjeta en vez de mentir mostrándolo activo.
    filtra_sucursal: bool = True
    visuales: tuple[str, ...] = field(default_factory=lambda: VISUALES)


def _ventas_por_dia(session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite):
    return sales_q.ventas_por_dia(
        session, empresa_id, desde=desde, hasta=hasta, sucursal_ids=sucursal_ids
    )


def _ventas_por_sucursal(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    return sales_q.ventas_por_sucursal(
        session, empresa_id, desde=desde, hasta=hasta, sucursal_ids=sucursal_ids
    )


def _top_productos(session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite):
    return sales_q.top_productos(
        session,
        empresa_id,
        desde=desde,
        hasta=hasta,
        sucursal_ids=sucursal_ids,
        limite=limite,
    )


def _compras_por_proveedor(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    # `orden_compra` cuelga de `almacen_destino_id`, no de una sucursal: la
    # compra es central. El filtro de sucursales no aplica a propósito.
    return purchases_q.compras_por_proveedor(
        session, empresa_id, desde=desde, hasta=hasta, limite=limite
    )


def _solicitudes_por_articulo(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    return inventory_q.solicitudes_resumen_para_negociacion(
        session, empresa_id, desde=desde, hasta=hasta, limit=limite
    )


def _consumos_omitidos(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    return inventory_q.consumos_omitidos(
        session, empresa_id, desde=desde, hasta=hasta, limite=limite
    )


def _disponible_negativo(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    return inventory_q.disponible_negativo(session, empresa_id, limite=limite)


def _salidas_sin_lote(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    return inventory_q.salidas_sin_lote(
        session, empresa_id, desde=desde, hasta=hasta, limite=limite
    )


def _ventas_por_hora(session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite):
    return sales_q.ventas_por_hora(
        session, empresa_id, desde=desde, hasta=hasta, sucursal_ids=sucursal_ids
    )


def _ventas_por_trabajador(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    """Compone `sales` (quién atendió, por `usuario_id`) con `rrhh` (cómo se
    llama). Ninguno de los dos conoce al otro: el cruce se hace acá, que es
    justamente para lo que existe este archivo."""
    filas = sales_q.ventas_por_usuario(
        session,
        empresa_id,
        desde=desde,
        hasta=hasta,
        sucursal_ids=sucursal_ids,
        limite=limite,
    )
    personal = rrhh_q.nombres_por_usuario(session, [f["usuario_id"] for f in filas])
    salida = []
    for fila in filas:
        # Un usuario sin trabajador (cuenta de servicio del hub, `agente_ia`)
        # sigue apareciendo: su venta es real. Se rotula como lo que es en
        # vez de desaparecer del ranking o inventarle un nombre.
        datos = personal.get(fila["usuario_id"])
        salida.append(
            {
                "trabajador": datos["nombre"] if datos else "(sin trabajador)",
                "cargo": datos["cargo"] if datos else "—",
                "cantidad": fila["cantidad"],
                "total": fila["total"],
            }
        )
    return salida


def _mesas_preferidas(session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite):
    return sales_q.mesas_preferidas(
        session,
        empresa_id,
        desde=desde,
        hasta=hasta,
        sucursal_ids=sucursal_ids,
        limite=limite,
    )


def _pedidos_demorados(session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite):
    return sales_q.pedidos_demorados(
        session,
        empresa_id,
        desde=desde,
        hasta=hasta,
        sucursal_ids=sucursal_ids,
        limite=limite,
    )


def _estado_caja(session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite):
    """Estado **actual**, no histórico: una caja abierta lo está ahora o no
    lo está. El rango de fechas del tablero no aplica y el catálogo lo
    declara para que la tarjeta lo diga en pantalla."""
    return accounting_q.estado_de_caja(session, empresa_id)


def _margen_por_producto(
    session: Session, empresa_id, *, desde, hasta, sucursal_ids, limite
):
    """Compone lo vendido (`sales`) con el costo de la receta (`inventory`).

    Un producto sin receta, o cuya receta no tiene insumos, sale con costo y
    margen en `None` — **nunca en cero**: cero se leería como "no cuesta
    nada" y mostraría 100 % de margen sobre un dato que en realidad falta.
    """
    filas = sales_q.vendido_por_producto(
        session,
        empresa_id,
        desde=desde,
        hasta=hasta,
        sucursal_ids=sucursal_ids,
        limite=limite,
    )
    costos = inventory_q.costo_unitario_de_recetas(
        session, [f["receta_id"] for f in filas if f["receta_id"]]
    )
    salida = []
    for fila in filas:
        unitario = costos.get(fila["receta_id"]) if fila["receta_id"] else None
        costo = unitario * fila["cantidad"] if unitario is not None else None
        margen = fila["ingreso"] - costo if costo is not None else None
        salida.append(
            {
                "producto": fila["producto"],
                "cantidad": fila["cantidad"],
                "ingreso": fila["ingreso"],
                "costo": costo,
                "margen": margen,
            }
        )
    return salida


CATALOGO: tuple[Reporte, ...] = (
    Reporte(
        codigo="ventas_por_dia",
        nombre="Ventas por día",
        descripcion="Serie diaria de ventas cobradas en el rango.",
        permiso="sales.leer",
        visual="lineas",
        etiqueta="fecha",
        valor="total",
        columnas=(
            Columna("fecha", "Fecha", "fecha"),
            Columna("cantidad", "Ventas", "numero"),
            Columna("total", "Total", "dinero"),
        ),
        consulta=_ventas_por_dia,
    ),
    Reporte(
        codigo="ventas_por_sucursal",
        nombre="Ventas por sucursal",
        descripcion="Ranking de sucursales por venta cobrada en el rango.",
        permiso="sales.leer",
        visual="barras",
        etiqueta="sucursal",
        valor="total",
        columnas=(
            Columna("sucursal", "Sucursal"),
            Columna("cantidad", "Ventas", "numero"),
            Columna("total", "Total", "dinero"),
        ),
        consulta=_ventas_por_sucursal,
    ),
    Reporte(
        codigo="top_productos",
        nombre="Productos más vendidos",
        descripcion="Ranking de productos por unidades vendidas en el rango.",
        permiso="sales.leer",
        visual="barras",
        etiqueta="producto",
        valor="cantidad",
        columnas=(
            Columna("producto", "Producto"),
            Columna("cantidad", "Unidades", "cantidad"),
            Columna("total", "Importe", "dinero"),
        ),
        consulta=_top_productos,
    ),
    Reporte(
        codigo="ventas_por_hora",
        nombre="Ventas por hora",
        descripcion=(
            "En qué franja del día se concentra la venta — base para "
            "dimensionar el turno. La hora es la del negocio, no UTC."
        ),
        permiso="sales.leer",
        visual="barras",
        etiqueta="hora",
        valor="total",
        columnas=(
            Columna("hora", "Hora"),
            Columna("cantidad", "Ventas", "numero"),
            Columna("total", "Total", "dinero"),
        ),
        consulta=_ventas_por_hora,
    ),
    Reporte(
        codigo="mesas_preferidas",
        nombre="Mesas preferidas",
        descripcion=(
            "Qué mesa pide más el cliente, por sucursal — para acomodar el "
            "salón según lo que la gente ya prefiere."
        ),
        permiso="sales.leer",
        visual="barras",
        etiqueta="mesa",
        valor="cantidad",
        columnas=(
            Columna("mesa", "Mesa"),
            Columna("cantidad", "Pedidos", "numero"),
            Columna("total", "Total", "dinero"),
        ),
        consulta=_mesas_preferidas,
    ),
    Reporte(
        codigo="ventas_por_trabajador",
        nombre="Ventas por trabajador",
        descripcion=(
            "Quién atendió más venta en el rango. Los usuarios que no son "
            "personal (cuenta de hub, agente IA) aparecen como "
            "«(sin trabajador)»."
        ),
        # Cruza `sales` con `rrhh`, así que exige los dos permisos: ver el
        # ranking es ver quién trabajó, no solo cuánto se vendió.
        permiso="rrhh.leer",
        visual="barras",
        etiqueta="trabajador",
        valor="total",
        columnas=(
            Columna("trabajador", "Trabajador"),
            Columna("cargo", "Cargo"),
            Columna("cantidad", "Ventas", "numero"),
            Columna("total", "Total", "dinero"),
        ),
        consulta=_ventas_por_trabajador,
    ),
    Reporte(
        codigo="margen_por_producto",
        nombre="Margen por producto",
        descripcion=(
            "Ingreso menos costo de receta (con merma), por producto. Un "
            "producto sin receta muestra costo y margen vacíos: el dato "
            "falta, no es cero."
        ),
        permiso="sales.leer",
        visual="tabla",
        etiqueta="producto",
        valor="margen",
        columnas=(
            Columna("producto", "Producto"),
            Columna("cantidad", "Unidades", "cantidad"),
            Columna("ingreso", "Ingreso", "dinero"),
            Columna("costo", "Costo", "dinero"),
            Columna("margen", "Margen", "dinero"),
        ),
        consulta=_margen_por_producto,
    ),
    Reporte(
        codigo="pedidos_demorados",
        nombre="Pedidos demorados",
        descripcion=(
            "Pedidos que superaron su tiempo en cocina y seguían sin salir. "
            "Guarda el umbral vigente al alertar, así que subirlo después no "
            "reescribe lo que en su momento fue una demora."
        ),
        permiso="sales.leer",
        visual="tabla",
        etiqueta="pedido",
        valor="minutos",
        columnas=(
            Columna("venta_id", "", "id", enlace="venta"),
            Columna("pedido", "Pedido"),
            Columna("fecha", "Fecha", "fecha"),
            Columna("sucursal", "Sucursal"),
            Columna("minutos", "Minutos", "numero"),
            Columna("umbral", "Umbral", "numero"),
            Columna("estado", "Estado al alertar"),
            Columna("items_pendientes", "Ítems pendientes", "numero"),
            Columna("atendida", "Atendida"),
        ),
        consulta=_pedidos_demorados,
    ),
    Reporte(
        codigo="estado_caja",
        nombre="Estado de caja",
        descripcion=(
            "Cajas abiertas ahora mismo, ordenadas por las que llevan más "
            "tiempo sin cerrar. Es una foto del presente: el rango de fechas "
            "no aplica."
        ),
        permiso="accounting.leer",
        visual="tabla",
        etiqueta="caja",
        valor="efectivo_esperado",
        # Una caja abierta lo está ahora; ni el rango ni la sucursal la
        # filtran (cuelga del punto de venta, no de la sucursal).
        filtra_sucursal=False,
        columnas=(
            Columna("caja", "Caja"),
            Columna("horas_abierta", "Horas abierta", "numero"),
            Columna("monto_apertura", "Apertura", "dinero"),
            Columna("efectivo_cobrado", "Cobrado en efectivo", "dinero"),
            Columna("movimientos_netos", "Ingresos − retiros", "dinero"),
            Columna("efectivo_esperado", "Efectivo esperado", "dinero"),
            Columna("diferencia_apertura", "Dif. al abrir", "dinero"),
        ),
        consulta=_estado_caja,
    ),
    Reporte(
        codigo="compras_por_proveedor",
        nombre="Compras por proveedor",
        descripcion=(
            "Cuánto se comprometió con cada proveedor en el rango "
            "(órdenes emitidas o recibidas). La compra es central: el filtro "
            "de sucursales no aplica."
        ),
        permiso="purchases.leer",
        visual="barras",
        etiqueta="proveedor",
        valor="total",
        filtra_sucursal=False,
        columnas=(
            Columna("proveedor", "Proveedor"),
            Columna("cantidad", "Órdenes", "numero"),
            Columna("total", "Total", "dinero"),
        ),
        consulta=_compras_por_proveedor,
    ),
    Reporte(
        codigo="solicitudes_por_articulo",
        nombre="Solicitudes de insumos por artículo",
        descripcion=(
            "Qué artículo pide más cada almacén — insumo para negociar "
            "volumen con proveedores."
        ),
        permiso="inventory.leer_solicitudes_externas",
        visual="tabla",
        etiqueta="articulo_nombre",
        valor="cantidad_total",
        filtra_sucursal=False,
        columnas=(
            Columna("articulo_nombre", "Artículo"),
            Columna("cantidad_total", "Cantidad pedida", "cantidad"),
            Columna("num_solicitudes", "Solicitudes", "numero"),
        ),
        consulta=_solicitudes_por_articulo,
    ),
    Reporte(
        codigo="consumos_omitidos",
        nombre="Consumos omitidos",
        descripcion=(
            "Movimientos que el sistema no hizo y por qué. Una venta nunca "
            "se frena por inventario, así que acá queda el stock que se fue "
            "de la realidad sin que nadie lo pidiera. El motivo dice dónde "
            "se arregla: configuración de la sucursal, catálogo, o stock."
        ),
        permiso="inventory.leer",
        visual="tabla",
        etiqueta="articulo",
        valor="cantidad",
        # La incidencia cuelga del almacén (o de ninguno, que es el caso
        # `sin_almacen`), no de una sucursal.
        filtra_sucursal=False,
        columnas=(
            Columna("fecha", "Fecha", "fecha"),
            Columna("origen", "Origen"),
            Columna("referencia", "Documento"),
            Columna("motivo", "Motivo"),
            Columna("articulo_id", "", "id", enlace="articulo"),
            Columna("articulo", "Artículo"),
            Columna("cantidad", "Cantidad", "cantidad"),
            Columna("detalle", "Detalle"),
        ),
        consulta=_consumos_omitidos,
    ),
    Reporte(
        codigo="disponible_negativo",
        nombre="Disponible negativo",
        descripcion=(
            "SKUs con más stock reservado que físico: promesas que el "
            "almacén no puede cumplir hoy (RN-INV-009). Es una foto del "
            "presente — el rango de fechas no aplica."
        ),
        permiso="inventory.leer",
        visual="tabla",
        etiqueta="articulo",
        valor="disponible",
        filtra_sucursal=False,
        columnas=(
            Columna("sku_id", "", "id", enlace="sku"),
            Columna("almacen", "Almacén"),
            Columna("articulo", "Artículo"),
            Columna("cantidad", "Físico", "cantidad"),
            Columna("reservado", "Reservado", "cantidad"),
            Columna("disponible", "Disponible", "cantidad"),
        ),
        consulta=_disponible_negativo,
    ),
    Reporte(
        codigo="salidas_sin_lote",
        nombre="Salidas sin lote",
        descripcion=(
            "Salidas de artículos con control de lote que ningún lote "
            "respalda: stock anterior al control, o el resto bloqueado por "
            "vencimiento. La salida es correcta; la trazabilidad de ese "
            "movimiento es la que se pierde."
        ),
        permiso="inventory.leer",
        visual="tabla",
        etiqueta="articulo",
        valor="cantidad",
        filtra_sucursal=False,
        columnas=(
            Columna("fecha", "Fecha", "fecha"),
            Columna("sku_id", "", "id", enlace="sku"),
            Columna("almacen", "Almacén"),
            Columna("articulo", "Artículo"),
            Columna("tipo", "Tipo"),
            Columna("cantidad", "Cantidad", "cantidad"),
            Columna("referencia", "Documento"),
        ),
        consulta=_salidas_sin_lote,
    ),
)

_POR_CODIGO = {r.codigo: r for r in CATALOGO}

# Tope de filas por consulta. Un ranking que devuelve 100k filas no es un
# reporte, es una descarga de la base por la puerta de atrás.
LIMITE_MAXIMO = 500
LIMITE_DEFECTO = 50


def obtener(codigo: str) -> Reporte | None:
    return _POR_CODIGO.get(codigo)


def visibles(permisos: Sequence[str]) -> list[Reporte]:
    """Los reportes que este usuario puede pedir. `*` (superusuario) ve
    todos — es el mismo criterio que el resto del RBAC."""
    if "*" in permisos:
        return list(CATALOGO)
    concedidos = set(permisos)
    return [r for r in CATALOGO if r.permiso in concedidos]


def ejecutar(
    reporte: Reporte,
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    sucursal_ids: Sequence[uuid.UUID] | None,
    limite: int,
) -> list[dict]:
    filas = reporte.consulta(
        session,
        empresa_id,
        desde=desde,
        hasta=hasta,
        sucursal_ids=sucursal_ids if reporte.filtra_sucursal else None,
        limite=min(limite, LIMITE_MAXIMO),
    )
    # Solo las columnas declaradas salen del backend: si una consulta
    # devuelve de más (un `id` interno, por ejemplo), no se filtra al cliente
    # por olvido de nadie.
    claves = [c.clave for c in reporte.columnas]
    return [{k: fila.get(k) for k in claves} for fila in filas]
