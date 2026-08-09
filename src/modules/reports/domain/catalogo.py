"""Catálogo de emisiones: qué hechos del ERP producen un reporte.

**Decisión central (ADR-033, heredada de ADR-024): la lista es cerrada y vive
en código, no en una tabla.** Una regla de distribución configura *a quién*
llega un reporte; nunca *qué datos* lee. Si el conjunto de emisiones fuera
administrable desde la API, quien puede crear reglas podría hacerse enviar
cualquier cosa que pase por el bus — y el RBAC del ERP dejaría de aplicar en
cuanto el cliente escribe la definición.

Cada emisión declara el permiso **de su módulo dueño**, no uno propio de
`reports`: así un `comprador` recibe reportes de compras y no de ventas sin
que haya que mantener una segunda matriz de permisos en paralelo.

`codigo` **es** el nombre del evento en el bus. Son la misma cosa y tener dos
identificadores para un hecho solo agrega una tabla de traducción que se
desincroniza. Si algún día un mismo evento tuviera que producir dos reportes
distintos, se resuelve con dos reglas sobre la misma emisión, no con dos
emisiones.

Agregar una emisión = una entrada acá + su fila en
`docs/architecture/events.md`. Este archivo es dominio puro: sin ORM, sin
FastAPI, sin red (`tests/test_arquitectura.py` lo exige).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from string import Formatter

# Qué tan fuerte se muestra. No es el tipo del hecho, es cuánto interrumpe.
# Mismos valores que `users.infrastructure.models.notificacion.NIVELES`: la
# entrega termina en esa bandeja y traducir entre dos escalas sería inventar
# una diferencia que no existe.
NIVELES = ("info", "aviso", "urgente")

# De dónde sale el tenant del reporte. La clave del payload es siempre
# `<ambito>_id`: `sucursal_id`, `almacen_id` o `empresa_id`.
AMBITOS = ("sucursal", "almacen", "empresa")

# Áreas que el ERP ya nombra por su cuenta: `inventory.conteo_vencido`
# publica `dirigido_a: ["almacen", "gerencia"]` y `devolucion` guarda
# `reporte_dirigido_a` en `almacen`|`comercial`. El seeder crea estas y las
# reglas por defecto apuntan a ellas.
AREAS_BASE = (
    ("almacen", "Almacén"),
    ("gerencia", "Gerencia"),
    ("comercial", "Comercial"),
    ("cocina", "Cocina"),
    ("caja", "Caja"),
    ("contabilidad", "Contabilidad"),
)

# Resolutores dinámicos: destinatarios que no se pueden listar de antemano
# porque dependen del estado del momento. Se implementan en
# `application/destinatarios.py`.
DINAMICOS = ("encargado_de_turno", "responsables_de_almacen")


@dataclass(frozen=True)
class Emision:
    """Un hecho del ERP que se reporta.

    `campos` es whitelist: solo eso se guarda en `reporte_emitido.datos`. Un
    payload que traiga de más no se filtra al cliente por olvido de nadie
    (RN-REP-003) — mismo mecanismo que `core.reportes.catalogo.ejecutar()`.
    """

    codigo: str
    nombre: str
    descripcion: str
    # El permiso del módulo dueño. Sin él no se abre el detalle, aunque el
    # reporte le haya sido entregado a quien pregunta (RN-REP-002).
    permiso: str
    campos: tuple[str, ...]
    # Plantilla de título. Solo puede usar claves de `campos` — lo verifica
    # `placeholders_invalidos()` y lo congela un test.
    titulo: str
    cuerpo: str = ""
    nivel: str = "aviso"
    ambito: str = "sucursal"
    areas_sugeridas: tuple[str, ...] = ()
    dinamicos_sugeridos: tuple[str, ...] = ()
    referencia_tipo: str = ""
    # Qué campo del payload es el id de la entidad referida.
    clave_referencia: str = ""

    @property
    def clave_ambito(self) -> str:
        return f"{self.ambito}_id"


def _placeholders(plantilla: str) -> set[str]:
    return {c for _, c, _, _ in Formatter().parse(plantilla) if c}


def placeholders_invalidos(emision: Emision) -> set[str]:
    """Claves que las plantillas usan y `campos` no declara.

    Una plantilla que interpola un campo no declarado explotaría al emitir
    —justo cuando ya no hay nadie mirando— o, peor, mostraría un dato que la
    whitelist decidió no guardar.
    """
    declarados = set(emision.campos)
    usados = _placeholders(emision.titulo) | _placeholders(emision.cuerpo)
    return usados - declarados


def proyectar(emision: Emision, payload: Mapping) -> dict:
    """El payload recortado a lo declarado. Lo que falte viaja como `None`:
    un campo ausente es un dato que faltó, no un campo que no existe."""
    return {clave: payload.get(clave) for clave in emision.campos}


def render(plantilla: str, datos: Mapping) -> str:
    """Interpola sin explotar. `format_map` sobre un dict normal levanta
    `KeyError` si falta una clave, y una emisión no puede perderse porque el
    emisor omitió un campo opcional."""
    if not plantilla:
        return ""
    return plantilla.format_map(_Faltante(datos))


class _Faltante(dict):
    def __missing__(self, clave: str) -> str:  # noqa: D105
        return "—"


CATALOGO: tuple[Emision, ...] = (
    # --- sales ---------------------------------------------------------------
    Emision(
        codigo="sales.pedido_demorado",
        nombre="Pedido demorado",
        descripcion=(
            "Un pedido superó su tiempo en cocina y seguía sin salir. Migrado "
            "desde el listener cableado de `users` (2026-08-08)."
        ),
        permiso="sales.leer",
        nivel="urgente",
        ambito="sucursal",
        campos=(
            "venta_id",
            "sucursal_id",
            "minutos_umbral",
            "minutos_transcurridos",
            "estado",
            "items_pendientes",
        ),
        titulo="Pedido demorado: {minutos_transcurridos} min (umbral {minutos_umbral})",
        cuerpo="Estado {estado}, {items_pendientes} ítem(s) pendiente(s).",
        areas_sugeridas=("cocina",),
        dinamicos_sugeridos=("encargado_de_turno",),
        referencia_tipo="venta",
        clave_referencia="venta_id",
    ),
    Emision(
        codigo="sales.descuento_aplicado",
        nombre="Descuento aplicado",
        descripcion=(
            "Alguien descontó sobre el total de una venta. Acto de autoridad "
            "(RN-AUD-005): lo pide un operario y lo autoriza un supervisor."
        ),
        permiso="sales.leer",
        ambito="sucursal",
        campos=("venta_id", "sucursal_id", "modo", "valor", "motivo", "autorizado_por"),
        titulo="Descuento {modo} de {valor} aplicado",
        cuerpo="Motivo: {motivo}.",
        areas_sugeridas=("gerencia",),
        referencia_tipo="venta",
        clave_referencia="venta_id",
    ),
    Emision(
        codigo="sales.venta_anulada",
        nombre="Venta anulada",
        descripcion="Una venta completa se anuló. Acto de autoridad (RN-AUD-005).",
        permiso="sales.leer",
        ambito="sucursal",
        campos=("venta_id", "sucursal_id", "usuario_id"),
        titulo="Venta anulada",
        areas_sugeridas=("gerencia",),
        referencia_tipo="venta",
        clave_referencia="venta_id",
    ),
    Emision(
        codigo="sales.lineas_anuladas",
        nombre="Líneas anuladas",
        descripcion=(
            "Se quitaron líneas de un pedido ya enviado a cocina. Acto de "
            "autoridad (RN-AUD-005) y merma probable."
        ),
        permiso="sales.leer",
        ambito="sucursal",
        campos=("venta_id", "sucursal_id", "autorizado_por", "motivo"),
        titulo="Líneas anuladas de un pedido en cocina",
        cuerpo="Motivo: {motivo}.",
        areas_sugeridas=("gerencia", "cocina"),
        referencia_tipo="venta",
        clave_referencia="venta_id",
    ),
    # --- inventory -----------------------------------------------------------
    Emision(
        codigo="inventory.stock_bajo_minimo",
        nombre="Stock bajo mínimo",
        descripcion=(
            "Un SKU cayó por debajo de su punto de reorden (RN-PRD-007). "
            "Migrado desde el listener cableado de `users` (2026-08-08)."
        ),
        permiso="inventory.leer",
        ambito="almacen",
        campos=("almacen_id", "sku_id", "cantidad", "stock_minimo"),
        titulo="Stock bajo mínimo: quedan {cantidad} (mínimo {stock_minimo})",
        areas_sugeridas=("almacen",),
        dinamicos_sugeridos=("responsables_de_almacen",),
        referencia_tipo="sku",
        clave_referencia="sku_id",
    ),
    Emision(
        codigo="inventory.lote_vencido_detectado",
        nombre="Lote vencido",
        descripcion=(
            "Un lote pasó su fecha de vencimiento y quedó bloqueado. Migrado "
            "desde el listener cableado de `users` (2026-08-08)."
        ),
        permiso="inventory.leer",
        nivel="urgente",
        ambito="almacen",
        campos=("lote_id", "almacen_id", "sku_id", "fecha_vencimiento", "cantidad"),
        titulo="Lote vencido el {fecha_vencimiento}: {cantidad} bloqueada(s)",
        areas_sugeridas=("almacen",),
        dinamicos_sugeridos=("responsables_de_almacen",),
        referencia_tipo="lote",
        clave_referencia="lote_id",
    ),
    Emision(
        codigo="inventory.conteo_vencido",
        nombre="Conteo cíclico vencido",
        descripcion=(
            "Una categoría pasó su fecha de conteo programada (RN-INV-021). El "
            "evento ya publicaba `dirigido_a: [almacen, gerencia]`; hasta este "
            "módulo nadie lo consumía."
        ),
        permiso="inventory.leer",
        ambito="almacen",
        campos=(
            "almacen_id",
            "categoria_id",
            "categoria",
            "frecuencia",
            "fecha_programada",
            "dias_atraso",
        ),
        titulo="Conteo vencido de {categoria}: {dias_atraso} día(s) de atraso",
        cuerpo="Frecuencia {frecuencia}, programado para el {fecha_programada}.",
        areas_sugeridas=("almacen", "gerencia"),
        referencia_tipo="categoria",
        clave_referencia="categoria_id",
    ),
    Emision(
        codigo="inventory.devolucion_a_proveedor",
        nombre="Devolución a proveedor",
        descripcion=(
            "Toda devolución genera reporte al área que corresponde "
            "(RN-INV-020). `reporte_dirigido_a` ya venía en el evento sin que "
            "nadie lo enrutara."
        ),
        permiso="inventory.leer",
        ambito="almacen",
        campos=(
            "devolucion_id",
            "almacen_id",
            "referencia_id",
            "motivo",
            "destino",
            "reporte_dirigido_a",
        ),
        titulo="Devolución a proveedor por {motivo}",
        cuerpo="Dirigida a {reporte_dirigido_a}.",
        areas_sugeridas=("almacen",),
        referencia_tipo="devolucion",
        clave_referencia="devolucion_id",
    ),
    Emision(
        codigo="inventory.devolucion_de_cliente",
        nombre="Devolución de cliente",
        descripcion="Devolución con origen en el cliente (RN-INV-020).",
        permiso="inventory.leer",
        ambito="almacen",
        campos=(
            "devolucion_id",
            "almacen_id",
            "referencia_id",
            "motivo",
            "destino",
            "reporte_dirigido_a",
        ),
        titulo="Devolución de cliente por {motivo}",
        cuerpo="Destino {destino}, dirigida a {reporte_dirigido_a}.",
        areas_sugeridas=("comercial",),
        referencia_tipo="devolucion",
        clave_referencia="devolucion_id",
    ),
    Emision(
        codigo="inventory.ajuste_fuera_margen",
        nombre="Ajuste fuera de margen",
        descripcion=(
            "Un ajuste de inventario superó el margen tolerado: insumo de "
            "auditoría (RN-AUD-004)."
        ),
        permiso="inventory.leer",
        nivel="urgente",
        ambito="almacen",
        campos=("ajuste_id", "almacen_id"),
        titulo="Ajuste de inventario fuera de margen",
        areas_sugeridas=("almacen", "gerencia"),
        referencia_tipo="ajuste",
        clave_referencia="ajuste_id",
    ),
    # --- accounting ----------------------------------------------------------
    Emision(
        codigo="accounting.cierre_caja_irregular",
        nombre="Cierre de caja irregular",
        descripcion=(
            "El cajón o los terminales no cuadraron al cerrar. `sucursal_id` "
            "se agregó al payload para este módulo (2026-08-08)."
        ),
        permiso="accounting.leer",
        nivel="urgente",
        ambito="sucursal",
        campos=(
            "cierre_caja_id",
            "sucursal_id",
            "descuadre_monto",
            "descuadre_tarjeta",
            "descuadre_atribucion",
        ),
        titulo="Cierre de caja irregular: descuadre de {descuadre_monto}",
        cuerpo="Descuadre de tarjetas {descuadre_tarjeta}. Atribuido a {descuadre_atribucion}.",
        areas_sugeridas=("contabilidad", "gerencia"),
        referencia_tipo="cierre_caja",
        clave_referencia="cierre_caja_id",
    ),
    Emision(
        codigo="accounting.pago_requiere_aprobacion",
        nombre="Pago sobre umbral",
        descripcion=(
            "Un pago a proveedor superó el umbral y espera aprobación. "
            "`empresa_id` se agregó al payload para este módulo (2026-08-08)."
        ),
        permiso="accounting.leer",
        ambito="empresa",
        campos=("movimiento_dinero_id", "empresa_id", "proveedor_id", "monto", "umbral"),
        titulo="Pago de {monto} espera aprobación (umbral {umbral})",
        areas_sugeridas=("gerencia", "contabilidad"),
        referencia_tipo="movimiento_dinero",
        clave_referencia="movimiento_dinero_id",
    ),
    # --- production ----------------------------------------------------------
    Emision(
        codigo="production.no_conformidad_detectada",
        nombre="No conformidad de producción",
        descripcion=(
            "Una orden de producción terminó fuera de norma (RN-PRD-015). "
            "`almacen_id` se agregó al payload para este módulo (2026-08-08)."
        ),
        permiso="production.leer",
        nivel="urgente",
        ambito="almacen",
        campos=("orden_produccion_id", "almacen_id", "resultado"),
        titulo="No conformidad de producción: {resultado}",
        areas_sugeridas=("gerencia", "almacen"),
        referencia_tipo="orden_produccion",
        clave_referencia="orden_produccion_id",
    ),
)

_POR_CODIGO = {e.codigo: e for e in CATALOGO}


def obtener(codigo: str) -> Emision | None:
    return _POR_CODIGO.get(codigo)


def codigos() -> tuple[str, ...]:
    return tuple(_POR_CODIGO)


def visibles(permisos: frozenset[str] | set[str]) -> list[Emision]:
    """Las emisiones que este usuario puede ver. `*` (superusuario) las ve
    todas — mismo criterio que el resto del RBAC."""
    if "*" in permisos:
        return list(CATALOGO)
    return [e for e in CATALOGO if e.permiso in permisos]
