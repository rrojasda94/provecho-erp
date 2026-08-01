/**
 * Cliente del PDV visto desde el navegador y tipos del contrato.
 *
 * Todo pasa por `/api/proxy` (ver `app/api/proxy/[...ruta]/route.ts`): el
 * token queda del lado del servidor. Los tipos espejan `openapi.json`; si
 * alguno se desincroniza, el error aparece acá y no como un `undefined`
 * silencioso en medio de un cobro.
 */

const BASE = "/api/proxy/api/v1";

export class ErrorApi extends Error {
  status: number;

  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
  }
}

async function pedir<T>(
  ruta: string,
  opciones: { metodo?: string; cuerpo?: unknown } = {},
): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, await mensajeDeError(respuesta));
  }
  return (await respuesta.json()) as T;
}

async function mensajeDeError(respuesta: Response): Promise<string> {
  try {
    const cuerpo = await respuesta.json();
    if (typeof cuerpo.detail === "string") return cuerpo.detail;
    if (Array.isArray(cuerpo.detail)) {
      return cuerpo.detail.map((d: { msg?: string }) => d.msg).join("; ");
    }
  } catch {
    // Cuerpo no-JSON: cae al mensaje genérico.
  }
  return `Error ${respuesta.status}`;
}

/** Cada operación crítica necesita su clave (RN-COM-002): un reintento por
 * red inestable no puede convertirse en un segundo cobro. */
export function claveIdempotencia(prefijo: string): string {
  return `${prefijo}-${crypto.randomUUID()}`;
}

// --- Tipos del contrato -----------------------------------------------------
export type ExtraDeCarta = {
  producto_comercial_id: string;
  nombre: string;
  precio_unitario: string;
  maximo: number | null;
};

export type ItemDeCarta = {
  producto_comercial_id: string;
  id_interno: string;
  nombre: string;
  categoria_id: string | null;
  precio_unitario: string;
  extras: ExtraDeCarta[];
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

  crearCliente: (cuerpo: {
    nombre: string;
    telefono?: string | null;
    numero_documento?: string | null;
    direccion?: string | null;
  }) => pedir<{ id: string }>("/sales/clientes", { metodo: "POST", cuerpo }),

  mediosPago: () => pedir<MedioPago[]>("/sales/medios-pago"),

  ventasDelDia: (sucursalId: string, estado?: string) =>
    pedir<Venta[]>(
      `/sales/ventas?sucursal_id=${sucursalId}${estado ? `&estado=${estado}` : ""}`,
    ),

  crearVenta: (cuerpo: Record<string, unknown>) =>
    pedir<Venta>("/sales/ventas", { metodo: "POST", cuerpo }),

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

  abrirCaja: (cuerpo: Record<string, unknown>) =>
    pedir<CajaAbierta>("/accounting/cajas/apertura", { metodo: "POST", cuerpo }),

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
