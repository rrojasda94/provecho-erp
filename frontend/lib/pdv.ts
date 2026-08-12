/**
 * Operaciones del PDV vistas desde el navegador y tipos del contrato.
 *
 * El transporte (proxy, errores, idempotencia) vive en `lib/cliente-api.ts`
 * y se re-exporta acá para no romper los imports existentes. Los tipos
 * espejan `openapi.json`; si alguno se desincroniza, el error aparece acá y
 * no como un `undefined` silencioso en medio de un cobro.
 */

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
  extras: ExtraDeVentaItem[];
};

export type MesaEnMapa = {
  id: string;
  numero: number;
  zona: string | null;
  capacidad: number | null;
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
};

export type ClienteNuevo = {
  nombre: string;
  telefono?: string | null;
  numero_documento?: string | null;
  direccion?: string | null;
  fecha_nacimiento?: string | null;
};

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
  comensales: number | null;
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
  referencia_atencion?: string | null;
  /** `consumo_personal` arma el pedido en cero y exige `consumo_motivo` +
   * la elevación de PIN del encargado (RN-COM-025). */
  tipo?: string;
  consumo_motivo?: string | null;
  autorizacion?: string;
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

export type AperturaCajaNueva = {
  punto_venta_id: string;
  /** Lo que el encargado dice entregar. Lo que el cajero cuenta va en
   * `detalle_denominaciones`; la diferencia la calcula el servidor
   * (RN-POS-011/012) y **nunca** se teclea. */
  monto_declarado: string;
  /** Valor del billete → piezas contadas. */
  detalle_denominaciones: Record<string, number>;
  autorizacion: string;
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

export type CierreCajaNuevo = {
  detalle_denominaciones: Record<string, number>;
  custodia: CustodiaDestino;
  autorizacion: string;
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

  mediosPago: () => pedir<MedioPago[]>("/sales/medios-pago"),

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

  itemsDeVenta: (ventaId: string) =>
    pedir<VentaItem[]>(`/sales/ventas/${ventaId}/items`),

  /** Quitar líneas de un pedido ya enviado a cocina exige PIN de supervisor
   * (RN-COM-020): el insumo ya se descontó, hay que reponerlo. */
  anularLineas: (
    ventaId: string,
    cuerpo: { venta_item_ids: string[]; motivo: string; autorizacion: string },
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

  registrarPago: (ventaId: string, cuerpo: PagoNuevo) =>
    pedir<{ id: string }>(`/sales/ventas/${ventaId}/pagos`, {
      metodo: "POST",
      cuerpo,
    }),

  precuenta: (ventaId: string) =>
    pedir<{ texto: string; total: string }>(`/sales/ventas/${ventaId}/precuenta`),

  comprobante: (ventaId: string) =>
    pedir<Record<string, unknown>>(`/sales/ventas/${ventaId}/comprobante`),

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
   * (`id`, `relevo_encargado_id`, `diferencia_reportada`...); `GET
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
