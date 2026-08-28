/**
 * Operaciones del PDV vistas desde el navegador y tipos del contrato.
 *
 * El transporte (proxy, errores, idempotencia) vive en `lib/cliente-api.ts`
 * y se re-exporta acá para no romper los imports existentes. Los tipos
 * espejan `openapi.json`; si alguno se desincroniza, el error aparece acá y
 * no como un `undefined` silencioso en medio de un cobro.
 */

import type { Ubicacion } from "@/components/direccion/ubicacion";
import type {
  TicketComprobante,
  TicketTexto,
} from "@/components/impresion/tipos";

import { pedir } from "./cliente-api";

export { ErrorApi, claveIdempotencia } from "./cliente-api";

// --- Tipos del contrato -----------------------------------------------------
export type ExtraDeCarta = {
  producto_comercial_id: string;
  nombre: string;
  precio_unitario: string;
  maximo: number | null;
  /** Grupo al que pertenece dentro de este producto. Con `grupo_minimo >= 1`
   * el grupo es obligatorio: no se puede agregar la línea sin elegir
   * (RN-COM-023). NULL = extra suelto, opcional. */
  grupo_id: string | null;
  grupo_nombre: string | null;
  grupo_minimo: number;
  grupo_maximo: number | null;
};

/** Un valor elegible de un atributo (ej. «Hawaiana» para «Mitad 1»). */
export type ValorDeCarta = {
  /** `producto_atributo_valor.id`: lo que viaja de vuelta en
   * `valores_variante_ids` y lo que nombra la condición de la receta. De este
   * id depende que la línea condicionada se active y descuente. */
  id: string;
  nombre: string;
  /** Se suma al precio de la línea (RN-COM-036). Normalmente "0". */
  precio_extra: string;
};

/** Una elección obligatoria para vender el producto (ADR-055/056).
 *
 * Distinto de un grupo de extras: el extra es un producto que nace como línea
 * cobrada aparte; un valor de atributo no crea línea — cambia qué se prepara,
 * activando las líneas condicionadas de la receta. Se elige exactamente uno
 * (RN-COM-040). */
export type AtributoDeCarta = {
  atributo_id: string;
  nombre: string;
  /** `radio` | `select`. Cosmético. */
  display: string;
  orden: number;
  valores: ValorDeCarta[];
};

/** Un insumo que el plato admite quitar ("sin cebolla"). No cambia el
 * precio; sí deja de descontarse del almacén (RN-PRD-004). */
export type Quitable = {
  articulo_id: string;
  nombre: string;
};

/** Tamaño/presentación con precio propio y completo (RN-COM-022). Elegir
 * una es obligatorio: la tarjeta padre no se vende. */
export type VarianteDeCarta = {
  producto_comercial_id: string;
  nombre: string;
  precio_unitario: string;
  orden: number;
  /** Los grupos y extras cuelgan del producto que se prepara, y con
   * presentaciones ese es la variante: los sabores de la Familiar no son los
   * de la Personal. Elegida la variante, estos mandan sobre los del padre. */
  extras: ExtraDeCarta[];
  /** Ídem para los atributos: en MitadXMitad las líneas cuelgan de «Pizza
   * MitadxMitad Familiar», no del padre. */
  atributos: AtributoDeCarta[];
  /** Pares de valores que no pueden ir juntos. Se guarda una fila y vale en
   * los dos sentidos, así que hay que comparar en ambas direcciones. */
  exclusiones: [string, string][];
};

export type ItemDeCarta = {
  producto_comercial_id: string;
  id_interno: string;
  nombre: string;
  categoria_id: string | null;
  categoria_nombre: string | null;
  /** Con variantes es el "desde": lo que se cobra sale de la elegida. */
  precio_unitario: string;
  variantes: VarianteDeCarta[];
  extras: ExtraDeCarta[];
  atributos: AtributoDeCarta[];
  exclusiones: [string, string][];
};

export type ExtraDeVentaItem = {
  id: string;
  producto_comercial_id: string;
  nombre: string;
  cantidad: string;
  precio_unitario: string;
};

/** Línea de una venta ya confirmada, tal como la devuelve
 * `GET /ventas/{id}/items` — id real, no el uuid local del borrador. */
export type VentaItem = {
  id: string;
  producto_comercial_id: string;
  nombre: string;
  cantidad: string;
  precio_unitario: string;
  grupo_cobro: number;
  /** Sin esto, reabrir la cuenta perdía la nota y el siguiente guardado la
   * borraba. */
  nota: string | null;
  extras: ExtraDeVentaItem[];
};

export type MesaEnMapa = {
  id: string;
  numero: number;
  zona: string | null;
  capacidad: number | null;
  pos_x: number;
  pos_y: number;
  venta_id: string | null;
  numero_orden: number | null;
  comensales: number | null;
  total: string;
};

export type ClienteBuscado = {
  id: string;
  tipo: string;
  nombre: string;
  telefono: string | null;
  numero_documento: string | null;
  direccion: string | null;
  identificado: boolean;
} & Ubicacion;

export type ClienteNuevo = {
  nombre: string;
  telefono?: string | null;
  numero_documento?: string | null;
  direccion?: string | null;
  fecha_nacimiento?: string | null;
} & Partial<Ubicacion>;

export type MedioPago = {
  id: string;
  nombre: string;
  tipo: string;
};

export type Venta = {
  id: string;
  numero_orden: number;
  fecha_orden: string;
  modalidad: string;
  estado: string;
  total: string;
  referencia_atencion: string | null;
  mesa_id: string | null;
  /** El número que ve el personal ("Mesa 7"). Va en el contrato porque el
   * PDV reabre una cuenta desde la pestaña de cuentas abiertas, sin pasar
   * por el mapa de salón: con solo el id, la pestaña decía "Mesa ?". */
  mesa_numero: number | null;
  comensales: number | null;
  /** Cómo se sirve el pedido: "servir todo junto", "bebidas al final". */
  nota_cocina: string | null;
  /** Descuento manual de la orden (RN-COM-017). El PDV lo muestra en el
   * ticket para que el cajero vea que está aplicado antes de cobrar. */
  descuento_modo: "porcentaje" | "monto" | null;
  descuento_valor: string | null;
  descuento_motivo: string | null;
  tipo: string;
  consumo_motivo: string | null;
};

/** Terminal de tarjeta de la sucursal, más los de emergencia del pool
 * (RN-POS-009/010). */
export type PosTarjeta = {
  id: string;
  serie: string;
  codigo_comercio: string;
  operador: string | null;
  estado: string;
  es_emergencia: boolean;
  sucursal_id: string | null;
};

/** Cómo quedó un POS al abrir el turno. El cierre solo le pide reporte de
 * lote a los que abrieron operativos: uno averiado no cobró nada. */
export type PosVerificado = {
  pos_tarjeta_id: string;
  serie: string;
  operativo: boolean;
  observacion: string | null;
};

export type CajaAbierta = {
  apertura_caja_id: string;
  punto_venta_id: string;
  cajero_id: string;
  monto_apertura: string;
  abierta_desde: string;
  pos_verificados: PosVerificado[] | null;
};

export type Autorizacion = {
  autorizacion: string;
  autorizado_por: string;
  expira_en_minutos: number;
};

export type CierreCaja = {
  id: string;
  apertura_caja_id: string;
  descuadre_monto: string;
  estado: string;
};

export type MovimientoCaja = {
  id: string;
  apertura_caja_id: string;
  tipo: string;
  monto: string;
  motivo: string;
};

// --- Cuerpos de request -----------------------------------------------------
/**
 * Los cinco cuerpos que hasta 2026-08-06 viajaban como
 * `Record<string, unknown>` — o sea, sin contrato del lado del cliente.
 * Ahí se coló el bug de ADR-025: el diálogo de apertura mandaba
 * `monto_apertura` cuando el servidor ya esperaba `monto_declarado`, y
 * nada lo dijo hasta que la caja devolvió 422 en producción. Con el tipo
 * puesto, `tsc` —que ya corre en CI vía `npm run build`— lo caza en el
 * punto de llamada, y `lib/contrato.test.ts` verifica que estos tipos y
 * `openapi.json` sigan diciendo lo mismo.
 *
 * Los montos van como `string`: son decimales y el servidor los acepta
 * así (`Decimal` en Pydantic). Mandarlos como `number` los hace pasar por
 * el flotante binario, y el redondeo de un cobro no es lugar para eso.
 */
export type ExtraDeVentaNueva = {
  producto_comercial_id: string;
  cantidad: string;
};

export type ItemDeVentaNueva = {
  producto_comercial_id: string;
  cantidad: string;
  grupo_cobro?: number;
  extras?: ExtraDeVentaNueva[];
  /** Insumos que esta línea NO lleva. El servidor rechaza los que la receta
   * no pone: no se puede quitar lo que el plato nunca tuvo. */
  sin_articulo_ids?: string[];
  /** Los valores de atributo elegidos (`producto_atributo_valor.id`): qué
   * mitades lleva la pizza. Es lo que activa las líneas condicionadas de la
   * receta, así que sin esto la venta se cobra sin descontar (RN-COM-040). */
  valores_variante_ids?: string[];
  /** Lo que el mesero le dice a cocina sobre ESTE plato ("bien cocida").
   * Hasta ADR-075 el PDV lo capturaba y no lo mandaba: el campo existía en
   * el diálogo y el dato moría ahí. */
  nota?: string | null;
};

export type VentaNueva = {
  sucursal_id: string;
  punto_venta_id: string;
  canal: string;
  modalidad: string;
  idempotency_key: string;
  items: ItemDeVentaNueva[];
  id?: string | null;
  cliente_id?: string | null;
  mesa_id?: string | null;
  comensales?: number | null;
  /** Cómo se sirve el pedido entero: "servir todo junto", "bebidas al
   * final". Del pedido y no de una línea. */
  nota_cocina?: string | null;
  referencia_atencion?: string | null;
  /** Adónde va el delivery y su ancla en el mapa. El costo del
   * reparto NO se manda: lo calcula el servidor (ADR-054), porque un
   * precio que viaja por el navegador es un precio que se edita. */
  direccion_entrega?: string | null;
  ubicacion_place_id?: string | null;
  ubicacion_lat?: string | number | null;
  ubicacion_lng?: string | number | null;
  ubicacion_plus_code?: string | null;
  ubicacion_distrito?: string | null;
  /** `consumo_personal` arma el pedido en cero y exige `consumo_motivo` +
   * la elevación de PIN del encargado (RN-COM-025). */
  tipo?: string;
  consumo_motivo?: string | null;
  autorizacion?: string;
};

export type CotizacionDeliveryIn = {
  sucursal_id: string;
  ubicacion_lat?: string | number | null;
  ubicacion_lng?: string | number | null;
  ubicacion_distrito?: string | null;
};

export type CotizacionDelivery = {
  distancia_km: string | null;
  costo: string;
  /** La distancia salió de la línea recta porque Google no contestó. */
  aproximada: boolean;
  derivar_a_externo: boolean;
  motivo: string | null;
};

/** Cuerpo de "mover productos" / "cobrar seleccionados" (RN-COM-043,
 * ADR-071). Un solo destino a la vez: otra orden ya abierta, una mesa
 * libre, o ninguno de los dos —solo `grupo_cobro`— para separar la cuenta
 * dentro de la misma orden. */
export type MoverLineasIn = {
  venta_item_ids: string[];
  destino_venta_id?: string | null;
  destino_mesa_id?: string | null;
  destino_comensales?: number | null;
  grupo_cobro?: number | null;
};

export type MoverLineasResultado = {
  origen: Venta;
  destino: Venta;
};

export type PagoNuevo = {
  medio_pago_id: string;
  monto: string;
  idempotency_key: string;
  id?: string | null;
  grupo_cobro?: number;
  receptor_nombre?: string | null;
  receptor_num_doc?: string | null;
  referencia_externa?: string | null;
};

/** Lo que se **manda** al verificar un POS al abrir. No es `PosVerificado`:
 * ese es lo que se **lee**, y trae además la `serie` que el servidor
 * resuelve. Confundirlos fue el primer hallazgo de tipar estos cuerpos. */
export type PosVerificadoNuevo = {
  pos_tarjeta_id: string;
  operativo: boolean;
  observacion?: string;
};

/** Sin `autorizacion`: el turno lo abre el cajero con su propia sesión
 * (RN-MDP-008, ADR-049). La firma con PIN quedó donde hay una entrega de
 * efectivo de verdad — la cadena de custodia del cierre. */
export type AperturaCajaNueva = {
  punto_venta_id: string;
  /** Lo que el encargado dice entregar. Lo que el cajero cuenta va en
   * `detalle_denominaciones`; la diferencia la calcula el servidor
   * (RN-POS-011/012) y **nunca** se teclea. */
  monto_declarado: string;
  /** Valor del billete → piezas contadas. */
  detalle_denominaciones: Record<string, number>;
  pos_verificados?: PosVerificadoNuevo[] | null;
};

/** A dónde va el efectivo al cerrar. Es un enum en la base (RN-MDP-005) y
 * el schema lo valida con `pattern`: un valor fuera de estos dos deja la
 * fila ilegible al leerla. */
export const CUSTODIAS = ["local_caja_fuerte", "traslado_contabilidad"] as const;
export type CustodiaDestino = (typeof CUSTODIAS)[number];

export const ATRIBUCIONES = ["cajero", "encargado", "tercero_reportado"] as const;
export type DescuadreAtribucion = (typeof ATRIBUCIONES)[number];

export const esCustodia = (v: string): v is CustodiaDestino =>
  (CUSTODIAS as readonly string[]).includes(v);

export const esAtribucion = (v: string): v is DescuadreAtribucion =>
  (ATRIBUCIONES as readonly string[]).includes(v);

/** Sin `autorizacion`, igual que la apertura: lo cierra el cajero solo. El
 * efectivo queda `en_caja` a su nombre y la entrega se firma después, en
 * `/contabilidad/caja`. */
export type CierreCajaNuevo = {
  detalle_denominaciones: Record<string, number>;
  custodia: CustodiaDestino;
  descuadre_atribucion?: DescuadreAtribucion | null;
  reportes_pos?: {
    pos_tarjeta_id: string;
    monto_lote: string;
    referencia?: string | null;
  }[];
};

export type MovimientoCajaNuevo = {
  tipo: "ingreso" | "retiro";
  monto: string;
  motivo: string;
  idempotency_key: string;
  /** Solo hace falta para retirar: meter plata al cajón no es la operación
   * de la que hay que desconfiar. */
  autorizacion?: string | null;
};

// --- Operaciones ------------------------------------------------------------
export type DescuentoIn = {
  /** `null` quita el descuento; los otros dos campos sobran ahí. */
  modo: "porcentaje" | "monto" | null;
  valor?: string;
  motivo?: string;
  autorizacion: string;
};

export type CuponCanjeado = {
  codigo: string;
  monto_descuento: string;
  venta: Venta;
};

/** Lo que el servidor devuelve de un borrador. `contenido` es opaco para
 * el contrato: la forma la decide el PDV (ADR-074). */
export type BorradorGuardado = {
  id: string;
  sucursal_id: string;
  punto_venta_id: string;
  usuario_id: string;
  contenido: unknown;
  actualizado_en: string;
};

export const api = {
  carta: (sucursalId: string, modalidad: string) =>
    pedir<ItemDeCarta[]>(
      `/sales/carta?sucursal_id=${sucursalId}&canal=pdv&modalidad=${modalidad}`,
    ),

  /** Qué se le puede pedir "sin" a este producto (RN-PRD-004). Sale de su
   * receta, así que depende de la variante elegida —una Familiar y una
   * Personal no llevan lo mismo— y se pide al abrir la línea, no con la
   * carta entera. */
  quitables: (productoId: string) =>
    pedir<Quitable[]>(`/sales/productos/${productoId}/quitables`),

  mapaMesas: (sucursalId: string) =>
    pedir<MesaEnMapa[]>(`/sales/mesas/mapa?sucursal_id=${sucursalId}`),

  buscarClientes: (q: string) =>
    pedir<ClienteBuscado[]>(`/sales/clientes/buscar?q=${encodeURIComponent(q)}`),

  crearCliente: (cuerpo: ClienteNuevo) =>
    pedir<{ id: string }>("/sales/clientes", { metodo: "POST", cuerpo }),

  // `direccion=cobro`: con lo que se le paga a un proveedor no se le cobra
  // a un comensal, y sin el filtro salía como pastilla en la caja.
  mediosPago: () => pedir<MedioPago[]>("/sales/medios-pago?direccion=cobro"),

  /** El endpoint devuelve el sobre paginado de ADR-026; el PDV quiere la
   * jornada entera y se le desenvuelve acá. `page_size` al techo (200): una
   * sucursal que pase de 200 ventas cobradas en un día perdería las más
   * viejas de la pestaña de cobrados, y ahí recién hace falta paginar la
   * pestaña en vez de subir un número. */
  ventasDelDia: async (sucursalId: string, estado?: string): Promise<Venta[]> => {
    const pagina = await pedir<{ items: Venta[] }>(
      `/sales/ventas?sucursal_id=${sucursalId}&page_size=200${
        estado ? `&estado=${estado}` : ""
      }`,
    );
    return pagina.items;
  },

  crearVenta: (cuerpo: VentaNueva) =>
    pedir<Venta>("/sales/ventas", { metodo: "POST", cuerpo }),

  /** Cuánto sale llevar el pedido a esa dirección, antes de aceptarlo.
   *
   * El número lo calcula el servidor con su propia clave de Google: esto
   * solo lo muestra. La **medición** gasta cuota de un proveedor pago, así
   * que se pide al cambiar el punto y no en cada tecla; sin ancla el servidor
   * devuelve la tarifa base sin preguntarle nada a Google, y hay que pedirla
   * igual: desde RN-COM-041 el reparto entra al total.
   */
  cotizarDelivery: (cuerpo: CotizacionDeliveryIn) =>
    pedir<CotizacionDelivery>("/sales/ventas/cotizar-delivery", {
      metodo: "POST",
      cuerpo,
    }),

  itemsDeVenta: (ventaId: string) =>
    pedir<VentaItem[]>(`/sales/ventas/${ventaId}/items`),

  /** Quitar líneas de un pedido ya enviado a cocina. Dentro de los 5 minutos
   * lo hace el cajero solo —es corregir un tecleo, RN-COM-029—; después el
   * insumo ya se usó y hay que reponerlo, así que lo firma un supervisor
   * (RN-COM-020). Por eso `autorizacion` es opcional: se manda recién cuando
   * el servidor dice que hace falta. */
  anularLineas: (
    ventaId: string,
    cuerpo: {
      venta_item_ids: string[];
      motivo: string;
      autorizacion?: string;
    },
  ) =>
    pedir<Venta>(`/sales/ventas/${ventaId}/anular-lineas`, {
      metodo: "POST",
      cuerpo,
    }),

  /** `autorizacion` solo hace falta cuando quien anula no tiene
   * `sales.anular` — el cajero, típicamente: la pide él y la firma un
   * supervisor con su PIN, igual que quitar una línea enviada. */
  anularVenta: (ventaId: string, autorizacion?: string) =>
    pedir<Venta>(`/sales/ventas/${ventaId}/anular`, {
      metodo: "POST",
      cuerpo: { autorizacion: autorizacion ?? null },
    }),

  /** Desbloqueo de la pantalla del PDV (RN-POS-014). No emite tokens: la
   * sesión de abajo sigue viva, con su caja abierta y su borrador — por eso
   * no sirve `login`, que la rotaría. 204 si el PIN es el correcto. */
  verificarPin: (pin: string) =>
    pedir<void>("/auth/verificar-pin", { metodo: "POST", cuerpo: { pin } }),

  /** Cómo se sirve el pedido entero (ADR-075): "servir todo junto",
   * "bebidas al final". Se puede cambiar con la orden ya en cocina, que es
   * cuando de verdad se pide. `null` la quita. */
  fijarNotaCocina: (ventaId: string, nota: string | null) =>
    pedir<Venta>(`/sales/ventas/${ventaId}/nota-cocina`, {
      metodo: "PUT",
      cuerpo: { nota },
    }),

  /** Canjea el cupón del cliente y lo apaga para siempre (ADR-061).
   *
   * **Sin PIN de supervisor**, a diferencia del descuento manual: el
   * descuento ya estaba prometido y el cupón *es* la autorización
   * (RN-PRM-007). Pedir una firma por cada cupón haría que la caja deje de
   * canjearlos. */
  canjearCupon: (ventaId: string, codigo: string) =>
    pedir<CuponCanjeado>(`/sales/ventas/${ventaId}/cupon`, {
      metodo: "POST",
      cuerpo: { codigo },
    }),

  /** Descuento manual sobre la orden (RN-COM-017). `modo: null` lo quita.
   *
   * **Con firma de supervisor**: acá se regala margen a criterio de alguien,
   * y `autorizacion` es el token de `POST /auth/autorizar` — quién autorizó
   * sale de ahí y nunca del cuerpo, o el reporte de descuentos dejaría de
   * valer (RN-AUD-005). El tope por permiso lo valida el servidor. */
  aplicarDescuento: (ventaId: string, cuerpo: DescuentoIn) =>
    pedir<Venta>(`/sales/ventas/${ventaId}/descuento`, {
      metodo: "POST",
      cuerpo,
    }),

  /** Guarda el ticket a medio armar contra el servidor (ADR-074).
   *
   * `PUT` con el id que la pestaña ya tiene: el navegador guarda con cada
   * cambio y no lleva la cuenta de si esta pestaña llegó antes, así que
   * repetirlo tiene que dejar el mismo estado y no una pestaña nueva. */
  guardarBorrador: (borradorId: string, puntoVentaId: string, contenido: unknown) =>
    pedir<BorradorGuardado>(`/sales/borradores/${borradorId}`, {
      metodo: "PUT",
      cuerpo: { punto_venta_id: puntoVentaId, contenido },
    }),

  /** Los borradores vivos de esta caja. Por punto de venta y no por usuario:
   * el relevo de turno sigue el pedido que dejó el anterior. */
  borradores: (puntoVentaId: string) =>
    pedir<BorradorGuardado[]>(
      `/sales/borradores?punto_venta_id=${puntoVentaId}`,
    ),

  descartarBorrador: (borradorId: string) =>
    pedir<void>(`/sales/borradores/${borradorId}`, { metodo: "DELETE" }),

  /** Suma líneas a una orden ya enviada (RN-COM-029). Sin autorización: la
   * mesa que pide de a poco no debería terminar con dos cuentas. */
  agregarLineas: (ventaId: string, items: VentaNueva["items"]) =>
    pedir<Venta>(`/sales/ventas/${ventaId}/items`, {
      metodo: "POST",
      cuerpo: { items },
    }),

  /** Mover productos entre pedidos, o separar la cuenta del mismo pedido
   * (RN-COM-043, ADR-071). Sin autorización: el producto sigue existiendo en
   * alguna orden abierta, no se repone inventario ni se deshace un cobro. */
  moverLineas: (ventaId: string, cuerpo: MoverLineasIn) =>
    pedir<MoverLineasResultado>(`/sales/ventas/${ventaId}/mover-lineas`, {
      metodo: "POST",
      cuerpo,
    }),

  registrarPago: (ventaId: string, cuerpo: PagoNuevo) =>
    pedir<{ id: string }>(`/sales/ventas/${ventaId}/pagos`, {
      metodo: "POST",
      cuerpo,
    }),

  /** `grupoCobro` pide la precuenta de una sola cuenta cuando la orden está
   * dividida (RN-COM-018); sin él, la de la venta entera. */
  precuenta: (ventaId: string, grupoCobro?: number) => {
    const ruta = `/sales/ventas/${ventaId}/precuenta`;
    return pedir<TicketTexto & { total: string }>(
      grupoCobro != null ? `${ruta}?grupo_cobro=${grupoCobro}` : ruta,
    );
  },

  comprobante: (ventaId: string) =>
    pedir<{ id: string; tipo: string; serie: string; correlativo: number }>(
      `/sales/ventas/${ventaId}/comprobante`,
    ),

  /** Lo que se manda a la ticketera de 80 mm (ADR-067). Existe aunque el
   * comprobante siga `pendiente` de llegar a SUNAT: el cliente se lleva su
   * papel en caja y no espera a un tercero (RN-COM-003). */
  ticketComprobante: (comprobanteId: string) =>
    pedir<TicketComprobante>(`/sales/comprobantes/${comprobanteId}/ticket`),

  /** POST y no GET a propósito: **cuenta** la impresión. La segunda y las
   * siguientes son reimpresiones y quedan auditadas — por eso el botón de
   * "Cuentas" reusa este endpoint en vez de uno de solo lectura. */
  comanda: (ventaId: string) =>
    pedir<TicketTexto & { numero_orden: number; reimpresion: boolean }>(
      `/kds/ventas/${ventaId}/comanda`,
      { metodo: "POST" },
    ),

  /** Por **sucursal** y no por empresa: es lo que el PDV necesita saber (¿mi
   * caja está abierta?) y lo único que el servidor le deja ver a quien opera
   * una caja sin darle de paso el efectivo de los demás locales. */
  cajasAbiertas: (sucursalId: string) =>
    pedir<CajaAbierta[]>(`/accounting/cajas/abiertas?sucursal_id=${sucursalId}`),

  /** Terminales que le toca verificar a esta sucursal al abrir: los suyos
   * más los de emergencia del pool, que es lo que devuelve el endpoint
   * cuando se le pasa la sucursal (RN-POS-009). */
  posDeSucursal: (sucursalId: string) =>
    pedir<PosTarjeta[]>(`/accounting/pos-tarjeta?sucursal_id=${sucursalId}`),

  /** `POST /cajas/apertura` devuelve el registro completo de la apertura
   * (`id`, `diferencia_reportada`, `pos_verificados`...); `GET
   * /cajas/abiertas` devuelve la vista liviana de la lista, con
   * `apertura_caja_id`. Se normaliza acá para que el resto del PDV — que
   * después necesita ese id para cerrar la caja o registrar propinas — no
   * tenga que saber de cuál de los dos endpoints vino el objeto. */
  abrirCaja: async (cuerpo: AperturaCajaNueva): Promise<CajaAbierta> => {
    const apertura = await pedir<{
      id: string;
      punto_venta_id: string;
      cajero_id: string;
      monto_apertura: string;
      pos_verificados: PosVerificado[] | null;
      created_at: string;
    }>("/accounting/cajas/apertura", { metodo: "POST", cuerpo });
    return {
      apertura_caja_id: apertura.id,
      punto_venta_id: apertura.punto_venta_id,
      cajero_id: apertura.cajero_id,
      monto_apertura: apertura.monto_apertura,
      abierta_desde: apertura.created_at,
      pos_verificados: apertura.pos_verificados,
    };
  },

  cerrarCaja: (aperturaCajaId: string, cuerpo: CierreCajaNuevo) =>
    pedir<CierreCaja>(`/accounting/cajas/apertura/${aperturaCajaId}/cierre`, {
      metodo: "POST",
      cuerpo,
    }),

  /** Propina en efectivo: ingreso de caja aparte, no toca la venta ni el
   * comprobante (decisión del usuario, 2026-08-01). */
  registrarMovimientoCaja: (
    aperturaCajaId: string,
    cuerpo: MovimientoCajaNuevo,
  ) =>
    pedir<MovimientoCaja>(
      `/accounting/cajas/apertura/${aperturaCajaId}/movimientos`,
      { metodo: "POST", cuerpo },
    ),

  /** El supervisor teclea su PIN en el terminal del cajero (RN-AUD-005).
   * Devuelve una elevación de minutos acotada a ese permiso. */
  autorizar: (username: string, pin: string, permiso: string) =>
    pedir<Autorizacion>("/auth/autorizar", {
      metodo: "POST",
      cuerpo: { username, pin, permiso },
    }),
};

export const soles = (monto: string | number): string =>
  `S/ ${Number(monto).toFixed(2)}`;
