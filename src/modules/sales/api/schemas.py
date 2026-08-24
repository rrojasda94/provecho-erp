"""DTOs (pydantic) del módulo sales."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.ubicacion import UbicacionMixin


# El precio NO viaja en el request: lo fija el servidor contra
# `lista_precio` (RN-PRC-003). `venta_item.precio_unitario` guarda el
# snapshot de lo resuelto.
class ExtraIn(BaseModel):
    producto_comercial_id: uuid.UUID
    cantidad: Decimal = Field(default=Decimal(1), gt=0)


class VentaItemIn(BaseModel):
    producto_comercial_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    # Cuenta a la que va la línea cuando el pedido se divide entre varios
    # pagadores. Omitirlo = todo en una sola cuenta (RN-COM-018).
    grupo_cobro: int = Field(default=1, ge=1)
    # Extras agregados a ESTA línea. Cada uno se guarda como línea propia
    # colgada de ella y hereda su grupo de cobro (RN-COM-021).
    extras: list[ExtraIn] = []
    # Restas: insumos de la receta que este plato NO lleva ("sin cebolla",
    # RN-PRD-004). Solo admite artículos que la receta usa; no cambian el
    # precio, sí el descuento de inventario.
    sin_articulo_ids: list[uuid.UUID] = []
    # Valores de atributo elegidos (ADR-055): `producto_atributo_valor.id`.
    # Deciden qué líneas condicionadas de la receta se descuentan
    # (RN-COM-037). Solo admite valores que el producto o su padre ofrecen.
    valores_variante_ids: list[uuid.UUID] = []


class VentaCreate(UbicacionMixin):
    sucursal_id: uuid.UUID
    punto_venta_id: uuid.UUID
    canal: str
    modalidad: str
    idempotency_key: str = Field(min_length=8, max_length=100)
    items: list[VentaItemIn] = Field(min_length=1)
    cliente_id: uuid.UUID | None = None
    # "Carlos", "Rappi #1042" — visible en KDS y comanda. Para modalidad
    # `mesa` el dato tipado es `mesa_id`.
    referencia_atencion: str | None = Field(default=None, max_length=50)
    # Adónde va el pedido. Los `ubicacion_*` del mixin son su ancla en el
    # mapa: con ella se cotiza la distancia de reparto (ADR-054). Sin ancla
    # el pedido se toma igual, con tarifa base y sin distancia.
    direccion_entrega: str | None = Field(default=None, max_length=255)
    mesa_id: uuid.UUID | None = None
    comensales: int | None = Field(default=None, ge=1)
    # Identificador generado por el cliente. El PDV puede crear la venta sin
    # conexión y conservar su id al llegar al servidor (ADR-009); si no lo
    # manda, lo genera el servidor como siempre.
    id: uuid.UUID | None = None
    # --- Consumo de personal (RN-COM-025) ------------------------------------
    # `tipo="consumo_personal"` arma el pedido con todas sus líneas en cero.
    # `autorizacion` es el token de `POST /auth/autorizar`: la comida
    # regalada la firma un encargado con su PIN, nunca el cajero que la pide.
    tipo: str = "venta"
    consumo_motivo: str | None = None
    autorizacion: str | None = None


class CotizacionDeliveryIn(UbicacionMixin):
    """A dónde hay que llevar el pedido, desde qué local.

    Se manda el ancla completa y no un `cliente_id`: en caja la mitad de los
    deliveries son de alguien que todavía no está registrado, y la dirección
    se acaba de escribir en el diálogo.
    """

    sucursal_id: uuid.UUID


class CotizacionDeliveryOut(BaseModel):
    """Lo que el cajero necesita para decidir antes de tomar el pedido."""

    distancia_km: Decimal | None
    costo: Decimal
    # True = la distancia salió de la línea recta porque Google no contestó.
    # El PDV lo muestra como "aprox." para que nadie discuta el monto como si
    # fuera una medición.
    aproximada: bool
    derivar_a_externo: bool
    motivo: str | None = None


class VentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    fecha_orden: date
    numero_orden: int
    canal: str
    modalidad: str
    estado: str
    total: Decimal
    referencia_atencion: str | None
    direccion_entrega: str | None = None
    # Lo cotizado al tomar la orden, congelado: la tarifa cambia y el
    # pedido de ayer no puede cambiar de precio.
    distancia_entrega_km: Decimal | None = None
    costo_entrega: Decimal | None = None
    mesa_id: uuid.UUID | None = None
    comensales: int | None = None
    descuento_modo: str | None = None
    descuento_valor: Decimal | None = None
    descuento_motivo: str | None = None
    tipo: str = "venta"
    consumo_motivo: str | None = None


class DescuentoCreate(BaseModel):
    """`modo=None` quita el descuento. Motivo y autorizador son obligatorios
    al aplicarlo: el reporte de descuentos necesita saber por qué y quién.

    `autorizacion` es el token que devuelve `POST /auth/autorizar` cuando el
    supervisor teclea su PIN en el terminal del cajero. **Quién autorizó sale
    de ahí, nunca del cuerpo**: un id suelto en el request sería una firma
    falsificable y el reporte de descuentos dejaría de valer (RN-AUD-005).
    """

    modo: str | None = None
    valor: Decimal | None = Field(default=None, gt=0)
    motivo: str | None = None
    autorizacion: str


class AnularLineasCreate(BaseModel):
    """Quitar líneas de una orden ya enviada a cocina.

    `autorizacion` es el token de `POST /auth/autorizar` y hace falta cuando
    la línea ya salió de la ventana de corrección (RN-COM-029): ahí el insumo
    se usó de verdad y reponerlo lo firma un supervisor (RN-COM-020). Dentro
    de la ventana es un error de tecleo y lo corrige el cajero solo.
    """

    venta_item_ids: list[uuid.UUID] = Field(min_length=1)
    motivo: str = Field(min_length=3, max_length=120)
    autorizacion: str | None = None


class AgregarLineasCreate(BaseModel):
    """Sumar líneas a una orden ya enviada a cocina (RN-COM-029). Mismo
    shape que los `items` del alta: una mesa que pide de a poco no debería
    obligar a abrir una orden nueva que después se cobra por separado."""

    items: list[VentaItemIn] = Field(min_length=1)


class AnularVentaIn(BaseModel):
    """Anular una orden entera. `autorizacion` es el token de
    `POST /auth/autorizar` y solo hace falta cuando quien la pide no tiene
    `sales.anular` — el cajero, típicamente: la pide él y la firma un
    supervisor con su PIN, igual que quitar una línea ya enviada
    (RN-COM-020)."""

    autorizacion: str | None = None


class PrecuentaOut(BaseModel):
    venta_id: uuid.UUID
    grupo_cobro: int | None
    total: Decimal
    texto: str


class PagoCreate(BaseModel):
    medio_pago_id: uuid.UUID
    monto: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    referencia_externa: str | None = None
    grupo_cobro: int = Field(default=1, ge=1)
    # Documento que el cliente pidió en caja. 11 dígitos = factura, 8 o
    # vacío = boleta (RN-CPP-003). Solo se usa al cerrarse la cuenta.
    receptor_num_doc: str | None = Field(default=None, max_length=11)
    receptor_nombre: str | None = Field(default=None, max_length=255)
    id: uuid.UUID | None = None


class PagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID
    medio_pago_id: uuid.UUID
    monto: Decimal
    grupo_cobro: int
    estado: str


class PuntoVentaCreate(BaseModel):
    """La caja de una sucursal. `serie_nc_*` son opcionales porque las cajas
    que ya existían no las tenían, pero sin ellas el ERP no emite notas de
    crédito de ese tipo y lo dice (RN-CPP-009).

    `modalidades_habilitadas=None` significa las tres (RN-MDC-001); una lista
    vacía no es "ninguna", es un error — una caja que no atiende de ninguna
    forma no tiene para qué existir.
    """

    sucursal_id: uuid.UUID
    canal: Literal["trabajador", "web", "kiosko"]
    politica_pago: Literal["adelantado", "al_finalizar"]
    serie_boleta: str = Field(max_length=10)
    serie_factura: str = Field(max_length=10)
    serie_nc_boleta: str | None = Field(default=None, max_length=10)
    serie_nc_factura: str | None = Field(default=None, max_length=10)
    hardware_id: str | None = Field(default=None, max_length=50)
    modalidades_habilitadas: list[Literal["mesa", "takeout", "delivery"]] | None = None


class PuntoVentaUpdate(BaseModel):
    """No lleva `sucursal_id`: la caja es del local donde se dio de alta, y
    sus comprobantes y aperturas cuelgan de ahí."""

    canal: Literal["trabajador", "web", "kiosko"] | None = None
    politica_pago: Literal["adelantado", "al_finalizar"] | None = None
    serie_boleta: str | None = Field(default=None, max_length=10)
    serie_factura: str | None = Field(default=None, max_length=10)
    serie_nc_boleta: str | None = Field(default=None, max_length=10)
    serie_nc_factura: str | None = Field(default=None, max_length=10)
    hardware_id: str | None = Field(default=None, max_length=50)
    modalidades_habilitadas: list[Literal["mesa", "takeout", "delivery"]] | None = None


class PuntoVentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    canal: str
    serie_boleta: str
    serie_factura: str
    serie_nc_boleta: str | None
    serie_nc_factura: str | None
    hardware_id: str | None
    modalidades_habilitadas: list | None
    politica_pago: str


# --- Mesas del salón --------------------------------------------------------
class MesaCreate(BaseModel):
    sucursal_id: uuid.UUID
    numero: int = Field(ge=1)
    zona: str | None = Field(default=None, max_length=50)
    capacidad: int | None = Field(default=None, ge=1)


class MesaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    numero: int
    zona: str | None
    capacidad: int | None
    activa: bool


class MesaEnMapaOut(BaseModel):
    """Una mesa y la orden abierta que tenga. `venta_id=None` = libre."""

    id: uuid.UUID
    numero: int
    zona: str | None
    capacidad: int | None
    venta_id: uuid.UUID | None
    numero_orden: int | None
    comensales: int | None
    total: Decimal


# --- Cliente creado desde caja ----------------------------------------------
class ClienteCreate(UbicacionMixin):
    """El tipo lo decide el documento: 11 dígitos crea cliente jurídico con
    RUC; el resto, uno natural con su persona.

    El documento es **opcional** para una persona natural — mucha gente no
    lo da en el mostrador — pero entonces el **teléfono es obligatorio**,
    porque algo tiene que servir para encontrarla después (RN-PTS-002). Para
    facturar a una empresa el RUC sí es obligatorio.
    """

    nombre: str = Field(min_length=1, max_length=255)
    telefono: str | None = Field(default=None, max_length=20)
    numero_documento: str | None = Field(default=None, max_length=11)
    email: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=255)
    fecha_nacimiento: date | None = None
    tipo_documento: str = "dni"


class ClienteDocumentoUpdate(BaseModel):
    """Completar el documento de un cliente registrado solo por teléfono."""

    numero_documento: str = Field(min_length=8, max_length=11)
    tipo_documento: str = "dni"


class ClienteUpdate(BaseModel):
    """Corrección de un cliente **jurídico**. Campo ausente o `null` = no tocar.

    No lleva nombre, teléfono ni dirección: en un cliente natural esos datos
    viven en su `persona` (RN-GEN-007) y se corrigen desde Personas. El
    documento tiene su propio endpoint (`PATCH /clientes/{id}/documento`),
    que aplica las reglas de identificación.
    """

    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    ruc: str | None = Field(default=None, pattern=r"^\d{11}$")
    contacto: str | None = Field(default=None, max_length=255)


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: str
    razon_social: str | None
    ruc: str | None
    persona_id: uuid.UUID | None


# --- Carga masiva de clientes (RN-PTS-007, ADR-052) ---
class ClienteImportadoIn(BaseModel):
    """Una fila de la hoja «Clientes», ya revisada por la pantalla.

    `id` y `accion` no son hechos: son **el permiso que una persona dio**. El
    servidor los vuelve a derivar contra la base antes de escribir.
    """

    id: uuid.UUID | None = None
    accion: Literal["crear", "actualizar", "omitir"] = "crear"
    nombre: str = Field(min_length=1, max_length=255)
    tipo_documento: str = Field(default="dni", max_length=20)
    documento: str = Field(default="", max_length=11)
    telefono: str | None = None
    email: str | None = None
    contacto: str | None = None
    fecha_nacimiento: str | None = None


class ImportarClientesIn(BaseModel):
    clientes: list[ClienteImportadoIn]


class ClienteRevisadoOut(BaseModel):
    fila: int
    id: uuid.UUID | None
    accion: str
    tipo: str
    nombre: str
    tipo_documento: str
    documento: str
    telefono: str
    email: str
    contacto: str
    fecha_nacimiento: str | None
    cambios: list[str]
    problemas: list[str]


class RevisionClientesOut(BaseModel):
    clientes: list[ClienteRevisadoOut]
    listas: int
    a_actualizar: int
    con_problema: int


class ImportadoOut(BaseModel):
    id: uuid.UUID
    nombre: str


class OmitidoOut(BaseModel):
    nombre: str
    motivo: str


class ResultadoImportacionOut(BaseModel):
    """El mismo sobre que usa inventory: crear, actualizar, omitir."""

    creadas: list[ImportadoOut]
    actualizadas: list[ImportadoOut]
    omitidas: list[OmitidoOut]


class ClienteBuscadoOut(UbicacionMixin):
    """Lo que el PDV necesita para pintar un resultado de búsqueda."""

    id: uuid.UUID
    tipo: str
    nombre: str
    telefono: str | None
    numero_documento: str | None
    direccion: str | None
    # False si no dio documento o dio el genérico: queda fuera de las
    # promociones para clientes registrados con documento (RN-PTS-002).
    identificado: bool
    # El back-office lo usa para mandar a la ficha de la persona: los datos
    # de un cliente natural se corrigen allá, no acá.
    persona_id: uuid.UUID | None = None


# --- Lote de sincronización del hub (ADR-009) -------------------------------
# Lo consume `core/sync` en `POST /sync/push`. Vive acá y no en `core`
# porque el contenido es dominio de sales: quien define qué es una venta
# válida es el módulo que la implementa.
class VentaItemSyncIn(BaseModel):
    """Ítem de una venta que YA se cobró en el hub. A diferencia del PDV en
    línea, acá el precio sí viaja: es el que el cliente pagó. Resolverlo de
    nuevo en la nube cambiaría el monto si la promoción venció entre el
    corte y la sincronización (RN-PRC-003 no admite recotizar lo cobrado).
    """

    producto_comercial_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)
    descuento: Decimal = Decimal(0)
    # Ausente en los lotes emitidos antes del cobro dividido: esa venta
    # tenía una sola cuenta.
    grupo_cobro: int = Field(default=1, ge=1)
    # Anidados bajo su línea padre para no perder de qué plato colgaban.
    extras: list["VentaItemSyncIn"] = []
    # Restas de la línea. Ausentes en lotes emitidos antes de RN-PRD-004:
    # esa venta no quitó nada. No se revalidan contra la receta —la venta ya
    # se preparó y la receta pudo cambiar durante el corte (ADR-009).
    sin_articulo_ids: list[uuid.UUID] = []
    # Valores de atributo de la línea. Ausentes en lotes emitidos antes de
    # ADR-055. Tampoco se revalidan contra el catálogo, por lo mismo.
    valores_variante_ids: list[uuid.UUID] = []


class VentaSyncIn(BaseModel):
    """Una venta ya ocurrida en el hub, tal cual, para reproducirla en la
    nube. Trae lo que la nube no puede reconstruir: identificador, día y
    número de orden que el cliente ya vio impresos, y quién la atendió."""

    id: uuid.UUID
    sucursal_id: uuid.UUID
    punto_venta_id: uuid.UUID
    canal: str
    modalidad: str
    usuario_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=100)
    fecha_orden: date
    numero_orden: int = Field(ge=1)
    estado: str
    items: list[VentaItemSyncIn] = Field(min_length=1)
    cliente_id: uuid.UUID | None = None
    referencia_atencion: str | None = Field(default=None, max_length=50)
    # Un delivery tomado sin internet sube con su dirección y lo que se
    # cobró por llevarla; sin esto la nube los perdería al sincronizar.
    direccion_entrega: str | None = Field(default=None, max_length=255)
    distancia_entrega_km: Decimal | None = None
    costo_entrega: Decimal | None = None
    mesa_id: uuid.UUID | None = None
    comensales: int | None = Field(default=None, ge=1)
    # El descuento del local viaja con su motivo y autorizador para que la
    # nube no lo pierda ni tenga que re-autorizarlo.
    descuento_modo: str | None = None
    descuento_valor: Decimal | None = None
    descuento_motivo: str | None = None
    descuento_autorizado_por: uuid.UUID | None = None
    # Consumo de personal (RN-COM-025), por el mismo motivo: sin el tipo la
    # nube reproduciría la comida del turno como una venta de S/ 0.00 —con
    # asiento de ingreso y lead atribuido—, y el encargado ya firmó en la
    # sucursal. Con default para los lotes emitidos antes de que existiera.
    tipo: str = "venta"
    consumo_motivo: str | None = None
    consumo_autorizado_por: uuid.UUID | None = None


class PagoSyncIn(BaseModel):
    id: uuid.UUID
    venta_id: uuid.UUID
    medio_pago_id: uuid.UUID
    monto: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    referencia_externa: str | None = None
    grupo_cobro: int = Field(default=1, ge=1)


class LoteSyncIn(BaseModel):
    ventas: list[VentaSyncIn] = []
    pagos: list[PagoSyncIn] = []


class ProductoCreate(BaseModel):
    id_interno: str = Field(min_length=1, max_length=4)
    # En una variante se ignora: hereda la marca del padre.
    marca_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=150)
    # NULL solo si el producto agrupa variantes: entonces la receta va en
    # cada hija (RN-COM-022).
    receta_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    # Si viene, este producto es una variante de aquel (Pizza Peperoni
    # Familiar cuelga de Pizza Peperoni).
    producto_padre_id: uuid.UUID | None = None
    # Orden de la tarjeta en el PDV: Personal, Mediana, Familiar.
    orden: int = 0
    empaque_id: uuid.UUID | None = None
    modalidades_empaque: list[str] | None = None
    # Un extra tiene su propia receta y se ejecuta en la sucursal: se suma
    # a la del producto al que se agrega (RN-COM-021). No sale suelto en la
    # carta.
    es_extra: bool = False


class GrupoOpcionCreate(BaseModel):
    """Grupo de extras del producto. `minimo >= 1` lo vuelve obligatorio: el
    PDV no deja agregar la línea hasta elegir (RN-COM-023)."""

    nombre: str = Field(min_length=1, max_length=50)
    minimo: int = Field(default=0, ge=0)
    maximo: int | None = Field(default=None, ge=1)
    orden: int = 0


class MarcaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str


class ExtraDeProductoOut(BaseModel):
    extra_id: uuid.UUID
    nombre: str
    receta_id: uuid.UUID | None
    maximo: int | None


class GrupoOpcionOut(BaseModel):
    id: uuid.UUID
    nombre: str
    minimo: int
    maximo: int | None
    orden: int
    extras: list[ExtraDeProductoOut] = []


class QuitableOut(BaseModel):
    """Un insumo que el plato admite quitar. Sale de la receta del producto,
    no de una configuración aparte."""

    articulo_id: uuid.UUID
    nombre: str


class VincularExtraCreate(BaseModel):
    """Habilita un extra sobre un producto. `maximo` es el tope de unidades
    del extra en una misma línea; NULL = sin tope. `grupo_id` lo mete en un
    grupo de opciones; sin grupo, el extra es siempre opcional."""

    extra_id: uuid.UUID
    maximo: int | None = Field(default=None, ge=1)
    grupo_id: uuid.UUID | None = None


class ProductoUpdate(BaseModel):
    nombre: str | None = None
    activo: bool | None = None
    receta_id: uuid.UUID | None = None
    # Único modo de dejar el producto sin receta: `receta_id=None` es
    # indistinguible de "no lo mandaron". Es el paso previo a venderlo por
    # presentaciones (RN-COM-022).
    quitar_receta: bool = False
    categoria_id: uuid.UUID | None = None
    orden: int | None = None
    empaque_id: uuid.UUID | None = None
    modalidades_empaque: list[str] | None = None
    # Dónde quedó el nodo en el lienzo (ADR-058): `{"x": 120, "y": 40}`.
    lienzo_pos: dict | None = None


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    id_interno: str
    marca_id: uuid.UUID
    nombre: str
    categoria_id: uuid.UUID | None = None
    receta_id: uuid.UUID | None = None
    producto_padre_id: uuid.UUID | None = None
    orden: int = 0
    activo: bool
    es_extra: bool = False
    empaque_id: uuid.UUID | None = None
    modalidades_empaque: list[str] | None = None
    lienzo_pos: dict | None = None


class ProductoDetalleOut(ProductoOut):
    """La ficha que edita la pantalla de catálogo: producto + variantes +
    grupos de extras, en una sola lectura."""

    variantes: list[ProductoOut] = []
    grupos: list[GrupoOpcionOut] = []
    extras_sueltos: list[ExtraDeProductoOut] = []


class MedioPagoCreate(BaseModel):
    # Derivado del JWT (ADR-004); solo un superusuario sin empresa asignada
    # puede indicarlo.
    empresa_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=50)
    direccion: str = "cobro"
    tipo: str
    comision_pct: Decimal = Decimal(0)


# --- Precios (server-side, RN-PRC-003) ---
class ListaPrecioCreate(BaseModel):
    marca_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=100)
    vigente_desde: date
    vigente_hasta: date | None = None
    sucursal_id: uuid.UUID | None = None
    canal: str | None = None
    modalidad: str | None = None
    es_promocional: bool = False


class ListaPrecioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    marca_id: uuid.UUID
    nombre: str
    sucursal_id: uuid.UUID | None
    canal: str | None
    modalidad: str | None
    es_promocional: bool
    vigente_desde: date
    vigente_hasta: date | None
    activa: bool


class PrecioCreate(BaseModel):
    producto_comercial_id: uuid.UUID
    monto: Decimal = Field(ge=0)


class PrecioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    lista_precio_id: uuid.UUID
    producto_comercial_id: uuid.UUID
    monto: Decimal


class ExtraDeCartaOut(BaseModel):
    """Extra ofrecible sobre un producto, con su precio ya resuelto para
    este ámbito (RN-COM-021)."""

    producto_comercial_id: uuid.UUID
    nombre: str
    precio_unitario: Decimal
    maximo: int | None
    # Grupo al que pertenece dentro de este producto. El cliente agrupa por
    # `grupo_id` y bloquea el agregado si un grupo con `grupo_minimo >= 1`
    # quedó sin elegir (RN-COM-023). NULL = extra suelto, opcional.
    grupo_id: uuid.UUID | None = None
    grupo_nombre: str | None = None
    grupo_minimo: int = 0
    grupo_maximo: int | None = None


class VarianteDeCartaOut(BaseModel):
    """Tamaño/presentación del producto, con precio propio y completo — no
    un recargo sobre el padre (RN-COM-022). Elegir una es obligatorio."""

    producto_comercial_id: uuid.UUID
    nombre: str
    precio_unitario: Decimal
    orden: int
    # Los grupos y extras cuelgan del producto que se prepara, y con
    # presentaciones ese es la variante: una Familiar y una Personal no
    # ofrecen los mismos sabores. Elegida la variante, estos mandan sobre
    # los del padre.
    extras: list[ExtraDeCartaOut] = []


class CartaItemOut(BaseModel):
    producto_comercial_id: uuid.UUID
    id_interno: str
    nombre: str
    categoria_id: uuid.UUID | None
    categoria_nombre: str | None = None
    # Con variantes, es el precio de la más barata ("desde S/ 25"): lo que
    # se cobra sale de la variante elegida, nunca de este campo.
    precio_unitario: Decimal
    variantes: list[VarianteDeCartaOut] = []
    # Los del padre. Un producto con variantes normalmente los tiene vacíos
    # (cuelgan de cada variante); se conserva para los productos simples.
    extras: list[ExtraDeCartaOut] = []


class VentaItemExtraOut(BaseModel):
    id: uuid.UUID
    producto_comercial_id: uuid.UUID
    nombre: str
    cantidad: Decimal
    precio_unitario: Decimal


class VentaItemOut(BaseModel):
    """Línea de una venta ya confirmada, para reabrirla en el PDV (mesa en
    curso) o para elegir qué anular (RN-COM-020)."""

    id: uuid.UUID
    producto_comercial_id: uuid.UUID
    nombre: str
    cantidad: Decimal
    precio_unitario: Decimal
    grupo_cobro: int
    extras: list[VentaItemExtraOut] = []


class ClientePublicoOut(BaseModel):
    id: uuid.UUID
    tipo: str
    nombre: str | None
    contacto: str | None


class MedioPagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    nombre: str
    tipo: str
    comision_pct: Decimal
    activo: bool


class NotaCreditoItemIn(BaseModel):
    venta_item_id: uuid.UUID
    cantidad: Decimal = Field(gt=0)


class NotaCreditoCreate(BaseModel):
    """Acredita un comprobante ya aceptado (RN-CPP-009).

    `motivo` es del catálogo 09 de SUNAT: 01 anulación de la operación, 02
    anulación por error en el RUC, 03 corrección por error en la
    descripción, 06 devolución total, 07 devolución por ítem.

    Sin `detalle` la nota es **total**. Con `detalle`, acredita solo esas
    líneas y esas cantidades.

    `repone_stock` es explícito porque no hay respuesta universal: un plato
    devuelto en cocina rara vez devuelve el insumo, y corregir el RUC de una
    factura no toca el inventario.
    """

    motivo: str = Field(pattern="^(01|02|03|06|07)$")
    motivo_descripcion: str | None = Field(default=None, max_length=255)
    detalle: list[NotaCreditoItemIn] | None = None
    repone_stock: bool = True


class ComprobanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID | None
    tipo: str
    serie: str
    correlativo: int
    # Cuenta que documenta y a quién se emitió: la pestaña de cobrados los
    # necesita para reimprimir el comprobante correcto de una venta dividida.
    grupo_cobro: int
    receptor_num_doc: str | None
    receptor_nombre: str | None
    estado_emision: str
    hash_proveedor: str | None
    detalle_emision: str | None
    intentos_emision: int
    # Nota de crédito: a qué documento corrige y por qué; y, en el
    # comprobante afectado, qué nota lo anuló.
    afecta_comprobante_id: uuid.UUID | None = None
    motivo_nc: str | None = None
    motivo_nc_descripcion: str | None = None
    anulado_por_nc_id: uuid.UUID | None = None


class EntregaOut(BaseModel):
    venta_id: str
    numero_orden: int
    modalidad: str
    estado_pedido: str
    ya_entregado: bool


# --- Atributos y variantes (ADR-055) -----------------------------------------
class AtributoCreate(BaseModel):
    """`modo_variante` decide si las combinaciones se materializan como
    variante vendible. `nunca` no genera ninguna fila: el valor viaja en la
    línea de venta y solo decide qué líneas de receta se descuentan."""

    nombre: str = Field(min_length=1, max_length=80)
    modo_variante: str = "nunca"
    display: str = "radio"
    orden: int = 0


class AtributoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    modo_variante: str | None = None
    display: str | None = None
    orden: int | None = None


class AtributoValorCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    orden: int = 0


class AtributoValorOut(BaseModel):
    id: uuid.UUID
    nombre: str
    orden: int
    activo: bool


class AtributoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    modo_variante: str
    display: str
    orden: int
    valores: list[AtributoValorOut]


class OfrecerAtributoIn(BaseModel):
    """Lista vacía = **todos** los valores del atributo, que es lo que quiere
    quien acaba de crearlo."""

    atributo_id: uuid.UUID
    valores: list[uuid.UUID] = []
    orden: int = 0


class PrecioExtraIn(BaseModel):
    precio_extra: Decimal = Field(ge=0)


class ExclusionIn(BaseModel):
    """Los dos valores no van juntos (RN-COM-038). Se guarda una sola fila:
    el par es simétrico y se lee en los dos sentidos."""

    valor_id: uuid.UUID
    excluye_id: uuid.UUID


class ValorDeProductoOut(BaseModel):
    id: uuid.UUID
    atributo_valor_id: uuid.UUID
    nombre: str
    precio_extra: Decimal
    activo: bool


class LineaDeAtributoOut(BaseModel):
    linea_id: uuid.UUID
    producto_comercial_id: uuid.UUID
    atributo_id: uuid.UUID
    nombre: str
    modo_variante: str
    display: str
    orden: int
    valores: list[ValorDeProductoOut]


class CombinacionOut(BaseModel):
    producto_comercial_id: str
    producto_atributo_valor_id: str


class ArbolProductoOut(ProductoDetalleOut):
    """Todo lo que el lienzo necesita en una sola llamada.

    Hereda de `ProductoDetalleOut` a propósito: con el interruptor
    `catalogo.modelo_odoo` apagado el lienzo sigue dibujando grupos y extras,
    y una sola forma de traer los datos evita que las dos pantallas se
    separen.
    """

    variantes_detalle: list[ProductoDetalleOut]
    atributos: list[LineaDeAtributoOut]
    exclusiones: list[list[str]]
    combinaciones: list[CombinacionOut]

