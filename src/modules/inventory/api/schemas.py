"""DTOs (pydantic) del módulo inventory."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Categorías ---
# `empresa_id` sale del JWT (ADR-004). Solo un superusuario sin empresa
# asignada puede indicarla; a cualquier otro usuario, una empresa distinta
# a la suya le responde 403.
class CategoriaCreate(BaseModel):
    empresa_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=100)
    asiento_contable_config: dict | None = None
    # Cada cuánto se cuenta esta categoría (RN-INV-007). NULL = fuera del
    # conteo cíclico.
    frecuencia_conteo: str | None = None


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    asiento_contable_config: dict | None = None
    frecuencia_conteo: str | None = None
    # Único modo de volver a NULL: sin esto, `frecuencia_conteo=None` es
    # indistinguible de "no la mandaron".
    quitar_frecuencia: bool = False


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    nombre: str
    frecuencia_conteo: str | None


# --- Unidades de medida ---
# Catálogo global, no por empresa (a diferencia de categoría/artículo): la
# conversión kilo↔gramo es la misma para cualquier empresa que use el ERP.
class CategoriaUdmCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)


class CategoriaUdmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    unidad_base_id: uuid.UUID | None


class UnidadMedidaCreate(BaseModel):
    categoria_udm_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=50)
    ratio: Decimal = Decimal(1)
    # Kilo necesita gramos (3), Unidad no admite fracción (0) — RN-GER-010,
    # no hay un default universal correcto; el default del modelo (3) es
    # solo el más común, quien crea la unidad decide el suyo.
    decimales: int = Field(ge=0, le=6, default=3)


class UnidadMedidaUpdate(BaseModel):
    nombre: str | None = None
    ratio: Decimal | None = None
    decimales: int | None = Field(default=None, ge=0, le=6)


class UnidadMedidaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    categoria_udm_id: uuid.UUID
    nombre: str
    ratio: Decimal
    # Con cuántos decimales se teclea una cantidad en esta unidad
    # (RN-GER-010): 3 para kilos, 0 para unidades sueltas.
    decimales: int


# --- Artículos ---
class ArticuloCreate(BaseModel):
    empresa_id: uuid.UUID | None = None
    id_interno: str = Field(min_length=1, max_length=4)
    nombre: str = Field(min_length=1, max_length=150)
    unidad_medida_id: uuid.UUID
    tipo: str = Field(max_length=30)
    categoria_id: uuid.UUID | None = None
    costo_promedio: Decimal = Decimal(0)
    # Perecible o trazable → su stock se mueve por lote y respeta FEFO.
    controla_lote: bool = False
    # Con cuántos días de anticipación este artículo se avisa "por vencer".
    dias_alerta_vencimiento: int | None = Field(default=None, ge=0, le=3650)


class ArticuloUpdate(BaseModel):
    """Campo ausente o `null` = no tocar.

    `unidad_medida_id` no está y no va a estar: el stock y las recetas ya
    cargadas están expresados en la unidad actual (ver `editar_articulo`).
    """

    # Un código de 4 caracteres mal tecleado se arrastra por toda la
    # operación —es lo que el almacenero lee en el estante— y hasta ahora
    # era inmutable.
    id_interno: str | None = Field(default=None, min_length=1, max_length=4)
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    categoria_id: uuid.UUID | None = None
    tipo: str | None = Field(default=None, max_length=30)
    costo_promedio: Decimal | None = None
    archivado: bool | None = None
    controla_lote: bool | None = None
    dias_alerta_vencimiento: int | None = Field(default=None, ge=0, le=3650)


class ArticuloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    id_interno: str
    nombre: str
    unidad_medida_id: uuid.UUID
    tipo: str
    categoria_id: uuid.UUID | None
    costo_promedio: Decimal
    archivado: bool
    controla_lote: bool
    dias_alerta_vencimiento: int | None


# --- SKU ---
class SkuCreate(BaseModel):
    articulo_id: uuid.UUID
    codigo: str = Field(min_length=1, max_length=50)
    codigo_barras: str | None = None


class SkuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    articulo_id: uuid.UUID
    codigo: str
    codigo_barras: str | None
    activo: bool


class SkuListadoOut(SkuOut):
    """El SKU con el nombre de su artículo: un selector que muestre solo el
    código obliga a adivinar qué es cada cosa."""

    articulo_nombre: str


class SkuDetalleOut(SkuOut):
    """El SKU con su artículo y su saldo por almacén.

    Es el destino de `inventory.stock_bajo_minimo`: quien abre el reporte
    quiere saber qué es, cuánto queda y dónde, sin encadenar tres pantallas.
    """

    articulo: ArticuloOut
    stock: list["StockDeSkuOut"] = Field(default_factory=list)


class StockDeSkuOut(BaseModel):
    almacen_id: uuid.UUID
    almacen: str
    cantidad: Decimal
    reservado: Decimal
    disponible: Decimal
    stock_minimo: Decimal | None
    bajo_minimo: bool


# --- Stock / movimientos ---
class MovimientoCreate(BaseModel):
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal  # con signo: + ingreso, − salida
    tipo: str
    referencia: str | None = None
    # Override del lote sugerido por FEFO; NULL deja que el ERP lo elija.
    lote_id: uuid.UUID | None = None
    # Obligatorio si `lote_id` no es el que FEFO sugería (RN-LOT-004).
    motivo_lote: str | None = Field(default=None, max_length=200)
    # Identificador generado por el cliente: permite que un dispositivo que
    # ya creó el movimiento sin conexión conserve su id (ADR-009).
    id: uuid.UUID | None = None


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    tipo: str
    lote_id: uuid.UUID | None


class StockOut(BaseModel):
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    # `cantidad` es el stock físico; `disponible` = físico − reservas
    # activas (RN-INV-009), y es contra ese que se compromete stock nuevo.
    cantidad: Decimal
    reservado: Decimal
    disponible: Decimal
    stock_minimo: Decimal | None
    bajo_minimo: bool


# --- Reservas ---
class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    tipo: str
    referencia_id: uuid.UUID | None
    motivo: str | None
    estado: str


# --- Solicitud de insumos ---
class SolicitudItemIn(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)


class SolicitudCreate(BaseModel):
    almacen_solicitante_id: uuid.UUID
    # Sin esto se usa el `almacen_abastecedor_id` configurado en el almacén.
    almacen_abastecedor_id: uuid.UUID | None = None
    items: list[SolicitudItemIn] = Field(min_length=1)
    observacion: str | None = Field(default=None, max_length=500)


class SolicitudItemCantidad(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class SolicitudAprobar(BaseModel):
    """Recorte por SKU; lo que no se menciona se aprueba tal cual se pidió.
    Aprobar 0 deja el ítem fuera y no reserva nada."""
    aprobadas: list[SolicitudItemCantidad] = []


class SolicitudItemCantidadIn(BaseModel):
    """Cantidad de un ítem del borrador. Solo el `sku_id` viaja en la ruta."""
    cantidad: Decimal = Field(gt=0)


class SolicitudItemAgregarIn(SolicitudItemCantidadIn):
    sku_id: uuid.UUID


class SolicitudItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sku_id: uuid.UUID
    cantidad_solicitada: Decimal
    cantidad_aprobada: Decimal | None
    cantidad_despachada: Decimal | None
    # Qué es urgencia y qué es decisión del local (RN-INV-024): en falso, el
    # almacenero sabe que ese ítem no está por faltar.
    bajo_minimo_al_pedir: bool = False


class SolicitudOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_solicitante_id: uuid.UUID
    almacen_abastecedor_id: uuid.UUID
    estado: str
    solicitado_por: uuid.UUID
    aprobado_por: uuid.UUID | None
    observacion: str | None


class SolicitudDetalleOut(SolicitudOut):
    items: list[SolicitudItemOut]


# --- Transferencias ---
class TransferenciaCreate(BaseModel):
    origen_almacen_id: uuid.UUID
    destino_almacen_id: uuid.UUID
    # Con solicitud, los ítems son opcionales: por defecto se despacha lo
    # aprobado. Sin solicitud (transferencia lateral) son obligatorios.
    solicitud_id: uuid.UUID | None = None
    items: list[SolicitudItemIn] = []
    transportista_id: uuid.UUID | None = None
    observacion: str | None = Field(default=None, max_length=500)


class TransferenciaRecibirItem(BaseModel):
    # Es el id del `transferencia_item`, no del SKU: una salida FEFO puede
    # repartir un mismo SKU entre varios lotes y cada lote se recibe aparte.
    item_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class TransferenciaRecibir(BaseModel):
    """Lo que no se menciona se recibe completo — salvo en una parcial."""
    items: list[TransferenciaRecibirItem] = []
    # `True` = llegó parte del envío y el resto sigue en tránsito. Explícito
    # a propósito: deducirlo de que falten ítems haría que un olvido cierre
    # la transferencia dando por perdido lo que todavía viene en camino.
    parcial: bool = False


class TransferenciaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sku_id: uuid.UUID
    lote_id: uuid.UUID | None
    cantidad_enviada: Decimal
    cantidad_recibida: Decimal | None
    diferencia: Decimal | None


class TransferenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    origen_almacen_id: uuid.UUID
    destino_almacen_id: uuid.UUID
    solicitud_id: uuid.UUID | None
    estado: str
    despachado_por: uuid.UUID
    recibido_por: uuid.UUID | None
    transportista_id: uuid.UUID | None
    observacion: str | None


class TransferenciaDetalleOut(TransferenciaOut):
    items: list[TransferenciaItemOut]


# --- Lotes ---
class LoteCreate(BaseModel):
    articulo_id: uuid.UUID
    # Sin código, el ERP lo deriva del vencimiento (RN-LOT-001).
    codigo: str | None = Field(default=None, max_length=50)
    fecha_vencimiento: date | None = None
    fecha_elaboracion: date | None = None
    origen: str = "carga_inicial"
    referencia: str | None = None
    condicion_almacenamiento: str | None = None


class LoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    articulo_id: uuid.UUID
    codigo: str
    fecha_vencimiento: date | None
    fecha_elaboracion: date | None
    origen: str
    referencia: str | None
    condicion_almacenamiento: str | None


class LoteDetalleOut(LoteOut):
    """El lote con sus saldos. Destino de `inventory.lote_vencido_detectado`:
    el reporte dice que se bloqueó, esto dice cuánto quedó y en qué almacén."""

    articulo: str
    saldos: list["StockLoteOut"] = Field(default_factory=list)


class StockLoteOut(BaseModel):
    """Saldo por lote — el listado que el picking lee en orden FEFO."""
    lote_id: uuid.UUID
    codigo: str
    articulo_id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    estado: str
    fecha_vencimiento: date | None
    vencido: bool
    # Dentro de la ventana de alerta: la del artículo
    # (`dias_alerta_vencimiento`) o la que impuso la consulta.
    por_vencer: bool = False


# --- Ajustes ---
class AjusteCreate(BaseModel):
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal  # delta con signo
    motivo: str
    # `dentro_margen` no se recibe: lo calcula el servidor contra el margen
    # aprobado para la empresa. Que lo declarara el cliente permitía silenciar
    # `inventory.ajuste_fuera_margen` desde el mismo request que lo provoca.


class AjusteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    motivo: str
    estado: str
    conteo_id: uuid.UUID | None
    solicitado_por: uuid.UUID
    aprobado_por: uuid.UUID | None
    dentro_margen: bool


class AjusteDetalleOut(AjusteOut):
    """Destino de `inventory.ajuste_fuera_margen`. Los nombres van resueltos:
    la pantalla que aprueba o rechaza no puede pedir cuatro endpoints más
    para saber qué artículo es y quién lo pidió."""

    articulo: str
    sku_codigo: str
    almacen: str
    solicitante: str
    aprobador: str | None


# --- Conteo cíclico ---
class ConteoCreate(BaseModel):
    almacen_id: uuid.UUID
    # NULL = conteo general de todo el almacén.
    categoria_id: uuid.UUID | None = None
    tipo: str = "rutina"
    observacion: str | None = Field(default=None, max_length=500)


class ConteoCantidad(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class ConteoCantidades(BaseModel):
    items: list[ConteoCantidad] = Field(min_length=1)


class ConteoAnulacion(BaseModel):
    # Obligatorio: anular es la salida para hacer desaparecer un conteo, así
    # que el porqué queda escrito en el propio conteo.
    motivo: str = Field(min_length=3, max_length=500)


class ConteoItemOut(BaseModel):
    sku_id: uuid.UUID
    cantidad_contada: Decimal | None
    # Ocultos al contador "a ciegas" (RN-INV-005): sin el permiso
    # `inventory.ver_stock_esperado` viajan en NULL.
    cantidad_sistema: Decimal | None = None
    diferencia: Decimal | None = None


class ConteoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    categoria_id: uuid.UUID | None
    tipo: str
    estado: str
    fecha_programada: date | None
    abierto_por: uuid.UUID
    cerrado_por: uuid.UUID | None
    observacion: str | None


class ConteoDetalleOut(ConteoOut):
    items: list[ConteoItemOut]


class ConteoCierreOut(BaseModel):
    conteo: ConteoOut
    # Ajustes solicitados por las diferencias — nacen `pendiente` y los
    # aprueba alguien distinto de quien contó (RN-INV-006).
    ajustes: list[AjusteOut]


class ProgramaConteoOut(BaseModel):
    almacen_id: uuid.UUID
    categoria_id: uuid.UUID
    categoria: str
    frecuencia: str
    ultimo_conteo: date | None
    proxima_fecha: date
    estado: str  # al_dia | vence_hoy | vencido
    dias_atraso: int


# --- Carga masiva de recetas (RN-COM-031) ---
class IngredienteImportadoIn(BaseModel):
    """Una línea de la hoja «Ingredientes», ya resuelta por la pantalla.

    `articulo_id` en `None` significa **omitir esta línea**: es lo que
    devuelve la pantalla cuando el usuario decidió no resolver ese insumo.
    """

    insumo: str = ""
    articulo_id: uuid.UUID | None = None
    # Texto y no Decimal: acepta aritmética tecleada ("450/3"), que evalúa
    # el servidor con los decimales de la unidad del insumo (RN-COM-024).
    cantidad: str
    merma_pct: Decimal = Decimal(0)


class RecetaImportadaIn(BaseModel):
    """Una fila de la hoja «Recetas», ya revisada por la pantalla.

    `id` y `accion` no son hechos: son **el permiso que una persona dio**. El
    servidor los vuelve a derivar contra la base antes de escribir (ADR-052).
    """

    id: uuid.UUID | None = None
    accion: Literal["crear", "actualizar", "omitir"] = "crear"
    # Qué hacer con los ingredientes que el archivo no menciona. Por defecto
    # se conservan: subir una hoja parcial por error no puede vaciar una
    # receta sin que alguien vea cuántas líneas pierde (ADR-052).
    ingredientes_ausentes: Literal["conservar", "quitar"] = "conservar"
    nombre: str = Field(min_length=1, max_length=150)
    rendimiento: Decimal = Field(gt=0)
    unidad_medida_id: uuid.UUID
    articulo_producido_id: uuid.UUID | None = None
    ingredientes: list[IngredienteImportadoIn] = []


class ImportarRecetasIn(BaseModel):
    recetas: list[RecetaImportadaIn]


class IngredienteRevisadoOut(BaseModel):
    fila: int
    insumo: str
    articulo_id: uuid.UUID | None
    cantidad: str
    merma_pct: str
    problemas: list[str]


class RecetaRevisadaOut(BaseModel):
    fila: int
    id: uuid.UUID | None
    accion: str
    ingredientes_ausentes: str
    nombre: str
    rendimiento: str
    unidad: str
    unidad_medida_id: uuid.UUID | None
    produce: str | None
    articulo_producido_id: uuid.UUID | None
    ingredientes: list[IngredienteRevisadoOut]
    cambios: list[str]
    se_quitarian: list[str]
    problemas: list[str]


class RevisionRecetasOut(BaseModel):
    """Lo que devuelve la fase 1. Declarado para que `openapi.json` lo
    documente: sin `response_model` salía como `{}` y los tipos del frontend
    no los verificaba nadie."""

    recetas: list[RecetaRevisadaOut]
    insumos_desconocidos: list[str]
    ingredientes_sin_receta: list[str]
    listas: int
    a_actualizar: int
    con_problema: int


class ImportadaOut(BaseModel):
    id: uuid.UUID
    nombre: str


class OmitidaOut(BaseModel):
    nombre: str
    motivo: str


class ResultadoImportacionOut(BaseModel):
    """El mismo sobre para las tres entidades: crear, actualizar, omitir."""

    creadas: list[ImportadaOut]
    actualizadas: list[ImportadaOut]
    omitidas: list[OmitidaOut]


# --- Carga masiva de artículos (RN-INV-023) ---
class SkuImportadoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    codigo_barras: str | None = None


class ArticuloImportadoIn(BaseModel):
    """Una fila de la hoja «Artículos», ya revisada por la pantalla.

    `unidad_medida_id` puede venir en `None` al actualizar: la unidad de un
    artículo que ya existe no se cambia por planilla (ADR-052).
    """

    id: uuid.UUID | None = None
    accion: Literal["crear", "actualizar", "omitir"] = "crear"
    codigo: str = Field(min_length=1, max_length=4)
    nombre: str = Field(min_length=1, max_length=150)
    tipo: str = Field(default="insumo", max_length=30)
    unidad_medida_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    costo_promedio: Decimal = Decimal(0)
    controla_lote: bool = False
    dias_alerta_vencimiento: int | None = None
    archivado: bool = False
    skus: list[SkuImportadoIn] = []


class ImportarArticulosIn(BaseModel):
    articulos: list[ArticuloImportadoIn]


class SkuRevisadoOut(BaseModel):
    fila: int
    codigo: str
    codigo_barras: str | None
    problemas: list[str]


class ArticuloRevisadoOut(BaseModel):
    fila: int
    id: uuid.UUID | None
    accion: str
    codigo: str
    nombre: str
    tipo: str
    unidad: str
    unidad_medida_id: uuid.UUID | None
    categoria: str
    categoria_id: uuid.UUID | None
    costo_promedio: str
    controla_lote: bool
    dias_alerta_vencimiento: int | None
    archivado: bool
    skus: list[SkuRevisadoOut]
    cambios: list[str]
    problemas: list[str]


class RevisionArticulosOut(BaseModel):
    articulos: list[ArticuloRevisadoOut]
    unidades_desconocidas: list[str]
    categorias_desconocidas: list[str]
    skus_sin_articulo: list[str]
    listas: int
    a_actualizar: int
    con_problema: int


# --- Recetas ---
class RecetaCreate(BaseModel):
    # Como en `ArticuloCreate`: el tenant manda y esto solo puede
    # confirmarlo. Un superusuario sin empresa asignada sí lo necesita.
    empresa_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=150)
    rendimiento_cantidad: Decimal = Field(gt=0)
    rendimiento_unidad_medida_id: uuid.UUID
    # Solo si la receta produce una subreceta inventariable; NULL si es el
    # BOM de un producto comercial de venta directa.
    articulo_id: uuid.UUID | None = None
    flexible: bool = False
    criterio_ajuste: str | None = Field(default=None, max_length=255)


class RecetaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    rendimiento_cantidad: Decimal | None = Field(default=None, gt=0)
    rendimiento_unidad_medida_id: uuid.UUID | None = None
    # Artículo (tipo `subreceta`) que esta receta produce. Exclusivo: dos
    # recetas produciendo lo mismo dejarían a `production` sin saber cuál
    # explotar.
    articulo_id: uuid.UUID | None = None
    flexible: bool | None = None
    criterio_ajuste: str | None = Field(default=None, max_length=255)


class RecetaItemCreate(BaseModel):
    """`cantidad` o `expresion`, no ambas obligatorias: si viene la
    operación ("1000/3"), el servidor la evalúa y el número que mande el
    cliente se ignora."""

    articulo_id: uuid.UUID
    cantidad: Decimal | None = None
    expresion: str | None = Field(default=None, max_length=60)
    merma_pct: Decimal = Field(default=Decimal(0), ge=0, lt=100)


class RecetaItemUpdate(BaseModel):
    cantidad: Decimal | None = None
    expresion: str | None = Field(default=None, max_length=60)
    merma_pct: Decimal | None = Field(default=None, ge=0, lt=100)


class RecetaEscalarIn(BaseModel):
    factor: Decimal = Field(gt=0)


class RecetaItemOut(BaseModel):
    id: uuid.UUID
    articulo_id: uuid.UUID
    articulo_nombre: str
    unidad_medida_id: uuid.UUID
    unidad_medida_nombre: str
    decimales: int
    cantidad: Decimal
    expresion: str | None
    merma_pct: Decimal
    costo_unitario: Decimal
    costo_linea: Decimal


class RecetaOut(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    nombre: str
    rendimiento_cantidad: Decimal
    rendimiento_unidad_medida_id: uuid.UUID
    rendimiento_unidad_medida_nombre: str | None
    articulo_id: uuid.UUID | None
    flexible: bool
    criterio_ajuste: str | None


class SolicitudResumenOut(BaseModel):
    articulo_id: uuid.UUID
    articulo_nombre: str
    sucursal_id: uuid.UUID | None
    cantidad_total: Decimal
    num_solicitudes: int


class RecetaDetalleOut(RecetaOut):
    items: list[RecetaItemOut]
    costo_total: Decimal


# --- Guía de remisión (RN-GDR-001..003) --------------------------------------
class GuiaRemisionCreate(BaseModel):
    """Lo que el sistema **no** puede saber del traslado: quién maneja, en
    qué vehículo, cuánto pesa la carga y qué día arranca el viaje.

    Los bienes no se piden: salen de `transferencia_item`, que es el
    registro de lo que de verdad se descontó del origen (RN-TRP-002).
    """

    chofer_nombres: str = Field(min_length=2, max_length=120)
    chofer_apellidos: str = Field(min_length=2, max_length=120)
    chofer_num_doc: str = Field(min_length=8, max_length=15)
    chofer_licencia: str = Field(min_length=6, max_length=20)
    vehiculo_placa: str = Field(min_length=6, max_length=10)
    peso_bruto_kg: Decimal = Field(gt=0)
    fecha_inicio_traslado: date | None = None
    # Catálogo 20 de SUNAT; `04` = traslado entre establecimientos propios,
    # que es el caso de toda transferencia entre almacenes del grupo.
    motivo_traslado: str = Field(default="04", pattern="^(01|04|13|18)$")
    # Catálogo 18; `02` = transporte privado (vehículo del grupo).
    modalidad_traslado: str = Field(default="02", pattern="^(01|02)$")
    observacion: str | None = Field(default=None, max_length=500)


class GuiaRemisionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    descripcion: str
    unidad: str


class GuiaDevolucionCreate(BaseModel):
    """Igual que la del traslado, más el lugar de destino: `proveedor` no
    tiene dirección modelada, así que se teclea como el chofer y la placa."""

    lugar_destino: str = Field(min_length=3, max_length=255)
    chofer_nombres: str = Field(min_length=2, max_length=120)
    chofer_apellidos: str = Field(min_length=2, max_length=120)
    chofer_num_doc: str = Field(min_length=8, max_length=15)
    chofer_licencia: str = Field(min_length=6, max_length=20)
    vehiculo_placa: str = Field(min_length=6, max_length=10)
    peso_bruto_kg: Decimal = Field(gt=0)
    fecha_inicio_traslado: date | None = None
    modalidad_traslado: str = Field(default="02", pattern="^(01|02)$")
    observacion: str | None = Field(default=None, max_length=500)


# --- Devoluciones -----------------------------------------------------------
class DevolucionItemIn(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    # Obligatorio al devolver a un proveedor un artículo con control de
    # lote: el reclamo tiene que decir qué mercadería se rechaza.
    lote_id: uuid.UUID | None = None


class DevolucionCreate(BaseModel):
    almacen_id: uuid.UUID
    origen: str = Field(pattern="^(proveedor|cliente)$")
    motivo: str
    # `proveedor_id` o `cliente_id`, según el origen.
    referencia_id: uuid.UUID | None = None
    # Solo en la devolución de un cliente: qué se hace con lo que volvió.
    destino: str | None = None
    observacion: str | None = Field(default=None, max_length=500)
    items: list[DevolucionItemIn] = Field(min_length=1)


class DevolucionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal
    lote_id: uuid.UUID | None


class DevolucionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    origen: str
    referencia_id: uuid.UUID | None
    motivo: str
    destino: str | None
    estado: str
    reporte_dirigido_a: str
    observacion: str | None
    # Quién movió el stock y quién lo revirtió. Sin esto la ficha decía qué
    # pasó pero no a quién preguntarle, que es la mitad de auditar.
    registrado_por: uuid.UUID | None
    anulado_por: uuid.UUID | None
    anulada_at: datetime | None


class DevolucionDetalleOut(DevolucionOut):
    items: list[DevolucionItemOut]


# --- Merma ------------------------------------------------------------------
class MermaCreate(BaseModel):
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    # RN-INV-012: qué la originó.
    motivo: str = Field(pattern="^(devolucion|rechazo_sucursal|auditoria)$")
    lote_id: uuid.UUID | None = None


class MermaResolver(BaseModel):
    # `desecho` saca el stock y lo asienta como pérdida; `reintegro` lo
    # devuelve a disponible (RN-INV-019).
    destino: str = Field(pattern="^(desecho|reintegro)$")


class MermaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    almacen_id: uuid.UUID
    sku_id: uuid.UUID
    lote_id: uuid.UUID | None
    cantidad: Decimal
    motivo: str | None
    estado: str
    referencia_id: uuid.UUID | None


class GuiaRemisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    # Exactamente uno de los dos: la guía la emite un traslado o una
    # devolución a proveedor.
    transferencia_id: uuid.UUID | None
    devolucion_id: uuid.UUID | None
    serie: str
    correlativo: int
    fecha_inicio_traslado: date
    motivo_traslado: str
    modalidad_traslado: str
    peso_bruto_kg: Decimal
    ruc_emisor: str
    ruc_receptor: str
    lugar_origen: str
    lugar_destino: str
    chofer_nombres: str
    chofer_apellidos: str
    chofer_num_doc: str
    chofer_licencia: str
    vehiculo_placa: str
    estado_emision: str
    detalle_emision: str | None
    observacion: str | None


class GuiaRemisionDetalleOut(GuiaRemisionOut):
    items: list[GuiaRemisionItemOut]


# --- Lote ascendente del hub (ADR-009) ---------------------------------------
class SolicitudSyncItemIn(SolicitudItemIn):
    """Ítem de una solicitud que se reproduce desde el hub.

    Trae la marca de urgencia porque la puso el local contra su propio stock
    (RN-INV-024) y recalcularla en la nube al reproducir el lote contaría
    otra cosa. No está en `SolicitudItemIn` a propósito: en el alta normal
    la calcula el servidor, y dejarla entrar por el cuerpo permitiría
    declararse urgente a uno mismo.
    """

    bajo_minimo_al_pedir: bool = False


class SolicitudSyncIn(BaseModel):
    """Solicitud creada en el local durante un corte. Viaja con su `id`
    client-generado: reproducirla dos veces no la duplica."""

    id: uuid.UUID
    almacen_solicitante_id: uuid.UUID
    almacen_abastecedor_id: uuid.UUID
    solicitado_por: uuid.UUID
    observacion: str | None = None
    items: list[SolicitudSyncItemIn] = Field(min_length=1)


class RecepcionSyncItemIn(BaseModel):
    item_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class RecepcionSyncIn(BaseModel):
    """El local recibió el camión sin conexión. La transferencia ya existe
    en la nube —la creó el central—, así que lo que sube es el hecho de
    haberla recibido, no la fila."""

    id: uuid.UUID
    recibido_por: uuid.UUID
    recibidas: list[RecepcionSyncItemIn] = []


class ConteoSyncItemIn(BaseModel):
    sku_id: uuid.UUID
    cantidad: Decimal = Field(ge=0)


class ConteoSyncIn(BaseModel):
    """Conteo cerrado (o anulado) en el local. Se reproduce en tres pasos
    porque el cierre es el que genera los ajustes en la nube."""

    id: uuid.UUID
    almacen_id: uuid.UUID
    categoria_id: uuid.UUID | None = None
    tipo: str = "rutina"
    estado: str = Field(pattern="^(cerrado|anulado)$")
    abierto_por: uuid.UUID
    cerrado_por: uuid.UUID | None = None
    observacion: str | None = None
    items: list[ConteoSyncItemIn] = []


class LoteInventorySyncIn(BaseModel):
    solicitudes: list[SolicitudSyncIn] = []
    recepciones: list[RecepcionSyncIn] = []
    conteos: list[ConteoSyncIn] = []


# --- Matriz de recetas (ADR-057) ---------------------------------------------
class MatrizRecetaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    rendimiento_cantidad: Decimal
    rendimiento_unidad_medida_id: uuid.UUID
    es_kit: bool


class MatrizInsumoOut(BaseModel):
    articulo_id: uuid.UUID
    nombre: str
    unidad_medida_id: uuid.UUID
    unidad: str
    decimales: int
    costo_promedio: Decimal


class MatrizCeldaOut(BaseModel):
    item_id: uuid.UUID
    receta_id: uuid.UUID
    articulo_id: uuid.UUID
    cantidad: Decimal
    expresion: str | None
    merma_pct: Decimal
    unidad_medida_id: uuid.UUID | None
    unidad: str
    decimales: int
    aplica_valores: list[str]
    orden: int


class MatrizOut(BaseModel):
    recetas: list[MatrizRecetaOut]
    insumos: list[MatrizInsumoOut]
    celdas: list[MatrizCeldaOut]


class CeldaIn(BaseModel):
    """Una celda de la grilla. La identidad es `(receta, insumo, condición)`,
    no un id de línea: es lo que permite pegar un rectángulo desde Excel, que
    no trae ids."""

    receta_id: uuid.UUID
    articulo_id: uuid.UUID
    # Vacío borra la línea: en una grilla, vaciar la celda es cómo se dice
    # "este insumo no va en esta receta".
    expresion: str | None = None
    merma_pct: Decimal = Decimal(0)
    unidad_medida_id: uuid.UUID | None = None
    aplica_valores: list[uuid.UUID] = []
    orden: int = 0


class GuardarMatrizIn(BaseModel):
    celdas: list[CeldaIn] = Field(min_length=1)


class ResultadoCeldaOut(BaseModel):
    receta_id: uuid.UUID | None = None
    articulo_id: uuid.UUID | None = None
    accion: str
    item_id: uuid.UUID | None = None
    cantidad: Decimal | None = None
    detalle: str | None = None


class GuardarMatrizOut(BaseModel):
    resultados: list[ResultadoCeldaOut]
    aplicadas: int
    con_problema: int

