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

/** Tamaño/presentación con precio propio y completo (RN-COM-022). Elegir
 * una es obligatorio: la tarjeta padre no se vende. */
export type VarianteDeCarta = {
  producto_comercial_id: string;
  nombre: string;
  precio_unitario: string;
  orden: number;
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
};

export type CajaAbierta = {
  apertura_caja_id: string;
  punto_venta_id: string;
  cajero_id: string;
  monto_apertura: string;
  abierta_desde: string;
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

// --- Operaciones ------------------------------------------------------------
export const api = {
  carta: (sucursalId: string, modalidad: string) =>
    pedir<ItemDeCarta[]>(
      `/sales/carta?sucursal_id=${sucursalId}&canal=pdv&modalidad=${modalidad}`,
    ),

  mapaMesas: (sucursalId: string) =>
    pedir<MesaEnMapa[]>(`/sales/mesas/mapa?sucursal_id=${sucursalId}`),

  buscarClientes: (q: string) =>
    pedir<ClienteBuscado[]>(`/sales/clientes/buscar?q=${encodeURIComponent(q)}`),

  crearCliente: (cuerpo: ClienteNuevo) =>
    pedir<{ id: string }>("/sales/clientes", { metodo: "POST", cuerpo }),

  mediosPago: () => pedir<MedioPago[]>("/sales/medios-pago"),

  ventasDelDia: (sucursalId: string, estado?: string) =>
    pedir<Venta[]>(
      `/sales/ventas?sucursal_id=${sucursalId}${estado ? `&estado=${estado}` : ""}`,
    ),

  crearVenta: (cuerpo: Record<string, unknown>) =>
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

  anularVenta: (ventaId: string) =>
    pedir<Venta>(`/sales/ventas/${ventaId}/anular`, { metodo: "POST" }),

  registrarPago: (ventaId: string, cuerpo: Record<string, unknown>) =>
    pedir<{ id: string }>(`/sales/ventas/${ventaId}/pagos`, {
      metodo: "POST",
      cuerpo,
    }),

  precuenta: (ventaId: string) =>
    pedir<{ texto: string; total: string }>(`/sales/ventas/${ventaId}/precuenta`),

  comprobante: (ventaId: string) =>
    pedir<Record<string, unknown>>(`/sales/ventas/${ventaId}/comprobante`),

  cajasAbiertas: (empresaId: string) =>
    pedir<CajaAbierta[]>(`/accounting/cajas/abiertas?empresa_id=${empresaId}`),

  /** `POST /cajas/apertura` devuelve el registro completo de la apertura
   * (`id`, `relevo_encargado_id`, `diferencia_reportada`...); `GET
   * /cajas/abiertas` devuelve la vista liviana de la lista, con
   * `apertura_caja_id`. Se normaliza acá para que el resto del PDV — que
   * después necesita ese id para cerrar la caja o registrar propinas — no
   * tenga que saber de cuál de los dos endpoints vino el objeto. */
  abrirCaja: async (cuerpo: Record<string, unknown>): Promise<CajaAbierta> => {
    const apertura = await pedir<{
      id: string;
      punto_venta_id: string;
      cajero_id: string;
      monto_apertura: string;
      created_at: string;
    }>("/accounting/cajas/apertura", { metodo: "POST", cuerpo });
    return {
      apertura_caja_id: apertura.id,
      punto_venta_id: apertura.punto_venta_id,
      cajero_id: apertura.cajero_id,
      monto_apertura: apertura.monto_apertura,
      abierta_desde: apertura.created_at,
    };
  },

  cerrarCaja: (aperturaCajaId: string, cuerpo: Record<string, unknown>) =>
    pedir<CierreCaja>(`/accounting/cajas/apertura/${aperturaCajaId}/cierre`, {
      metodo: "POST",
      cuerpo,
    }),

  /** Propina en efectivo: ingreso de caja aparte, no toca la venta ni el
   * comprobante (decisión del usuario, 2026-08-01). */
  registrarMovimientoCaja: (
    aperturaCajaId: string,
    cuerpo: Record<string, unknown>,
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
