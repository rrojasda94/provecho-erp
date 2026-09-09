/**
 * Cliente y tipos del módulo `delivery` (ADR-098). Espeja
 * `src/modules/delivery/api/schemas.py` — lo comparten la PWA del
 * repartidor (`app/reparto/`) y el tablero de despacho (`app/(app)/delivery/`):
 * las dos leen la misma vista compuesta `RutaConParadas`, con distintos
 * filtros (una ruta, las de la sucursal) y distintos permisos.
 */

import { type Pagina } from "@/lib/api";

import { pedir } from "./cliente-api";

export type EstadoRuta = "planificada" | "en_curso" | "finalizada" | "cancelada";
export type EstadoEntrega =
  | "pendiente"
  | "asignada"
  | "en_ruta"
  | "entregada"
  | "fallida"
  | "cancelada";
export type MotivoFallo =
  | "cliente_ausente"
  | "direccion_errada"
  | "rechazo"
  | "no_contesta"
  | "otro";

export const MOTIVOS_FALLO: MotivoFallo[] = [
  "cliente_ausente",
  "direccion_errada",
  "rechazo",
  "no_contesta",
  "otro",
];

export const ESTADOS_ENTREGA: EstadoEntrega[] = [
  "pendiente",
  "asignada",
  "en_ruta",
  "entregada",
  "fallida",
  "cancelada",
];

export const ETIQUETA_ESTADO_ENTREGA: Record<EstadoEntrega, string> = {
  pendiente: "Pendiente",
  asignada: "Por salir",
  en_ruta: "En camino",
  entregada: "Entregada",
  fallida: "No se pudo entregar",
  cancelada: "Cancelada",
};

export const ETIQUETA_MOTIVO: Record<MotivoFallo, string> = {
  cliente_ausente: "El cliente no estaba",
  direccion_errada: "La dirección está mal",
  rechazo: "El cliente lo rechazó",
  no_contesta: "No contesta el teléfono ni el timbre",
  otro: "Otro motivo",
};

export type ParadaReparto = {
  entrega_id: string;
  venta_id: string;
  orden_parada: number | null;
  estado: EstadoEntrega;
  numero_orden: number | null;
  direccion_entrega: string | null;
  destino_lat: string | number | null;
  destino_lng: string | number | null;
  cliente_nombre: string | null;
  cliente_telefono: string | null;
  monto_a_cobrar: string | number | null;
  eta_at: string | null;
  motivo_fallo: MotivoFallo | null;
  /** Mismo enlace que recibe el cliente por WhatsApp — `null` sin token o sin
   * `DELIVERY_URL_PUBLICA` configurada. */
  enlace_seguimiento: string | null;
};

export type RutaConParadas = {
  id: string;
  sucursal_id: string;
  repartidor_id: string;
  repartidor_nombre: string | null;
  estado: EstadoRuta;
  hora_salida: string | null;
  origen_lat: string | number;
  origen_lng: string | number;
  distancia_m: number | null;
  duracion_seg: number | null;
  polyline: string | null;
  ultima_lat: string | number | null;
  ultima_lng: string | number | null;
  ultima_posicion_at: string | null;
  paradas: ParadaReparto[];
};

export type VentaLista = {
  id: string;
  sucursal_id: string;
  numero_orden: number;
  fecha_orden: string;
  cliente_id: string | null;
  direccion_entrega: string | null;
  ubicacion_lat: string | number | null;
  ubicacion_lng: string | number | null;
  distancia_entrega_km: string | number | null;
};

export type Tablero = {
  sin_asignar: VentaLista[];
  rutas: RutaConParadas[];
  /** Si es `false`, el aviso automático por WhatsApp no está configurado:
   * el tablero solo puede ofrecer copiar el enlace o mandarlo por `wa.me`. */
  whatsapp_habilitado: boolean;
};

export type VehiculoTipo = "moto" | "bicicleta" | "auto" | "a_pie";

/**
 * Enlace `wa.me` para el fallback manual del tablero (ADR-098): mismo
 * criterio de normalización que `shared.integrations.whatsapp.client.
 * normalizar_telefono` — deja solo dígitos y antepone "51" si quedó un
 * móvil local de 9 dígitos. `null` si no queda un número usable.
 */
export function enlaceWhatsApp(telefono: string | null, texto: string): string | null {
  const digitos = (telefono ?? "").replace(/\D/g, "").replace(/^0+/, "");
  if (!digitos) return null;
  const numero = digitos.length === 9 ? `51${digitos}` : digitos;
  return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
}

export const VEHICULOS: VehiculoTipo[] = ["moto", "bicicleta", "auto", "a_pie"];

export const ETIQUETA_VEHICULO: Record<VehiculoTipo, string> = {
  moto: "Moto",
  bicicleta: "Bicicleta",
  auto: "Auto",
  a_pie: "A pie",
};

export type RepartidorCandidato = {
  trabajador_id: string;
  usuario_id: string;
  nombre: string;
  cargo: string;
  sucursal_id: string | null;
};

export type Repartidor = {
  id: string;
  empresa_id: string;
  sucursal_id: string;
  trabajador_id: string;
  usuario_id: string;
  nombre: string | null;
  vehiculo_tipo: VehiculoTipo;
  placa: string | null;
  telefono: string | null;
  activo: boolean;
};

export type RepartidorEnvio = {
  trabajador_id: string;
  sucursal_id: string;
  vehiculo_tipo: VehiculoTipo;
  placa?: string | null;
  telefono?: string | null;
};

export type RepartidorCambios = {
  sucursal_id?: string;
  vehiculo_tipo?: VehiculoTipo;
  placa?: string | null;
  telefono?: string | null;
  activo?: boolean;
};

export type EntregaHistorial = {
  id: string;
  venta_id: string;
  sucursal_id: string;
  ruta_id: string | null;
  repartidor_id: string | null;
  repartidor_nombre: string | null;
  orden_parada: number | null;
  estado: EstadoEntrega;
  intentos: number;
  eta_at: string | null;
  tramo_distancia_m: number | null;
  tramo_duracion_seg: number | null;
  destino_lat: string | number | null;
  destino_lng: string | number | null;
  numero_orden: number | null;
  direccion_entrega: string | null;
  cliente_nombre: string | null;
  fecha_entrega: string | null;
  entregado_por: string | null;
  motivo_fallo: MotivoFallo | null;
  motivo_detalle: string | null;
  resultado_lat: string | number | null;
  resultado_lng: string | number | null;
  observacion: string | null;
};

export type PosicionEnvio = {
  lat: number;
  lng: number;
  precision_m?: number | null;
  /** Reloj del teléfono — ver `PosicionIn` en el backend. */
  registrado_at: string;
};

export type EntregarEnvio = {
  lat?: number | null;
  lng?: number | null;
  /** JPEG en base64, sin el encabezado `data:image/jpeg;base64,`. */
  foto?: string | null;
  observacion?: string | null;
};

export type FallarEnvio = {
  motivo: MotivoFallo;
  /** Obligatorio si `motivo === "otro"` (RN-DLV-003). */
  detalle?: string | null;
  lat?: number | null;
  lng?: number | null;
  foto?: string | null;
};

export type RutaEnvio = {
  sucursal_id: string;
  repartidor_id: string;
  venta_ids: string[];
  optimizar?: boolean;
};

type RutaAck = { id: string; estado: EstadoRuta };
type EntregaAck = { id: string; estado: EstadoEntrega };

/** Los únicos parámetros con valor que entran a la URL — `undefined` no se
 * manda, para no pedir `repartidor_id=undefined` por accidente.
 *
 * Sin el `?` inicial a propósito: cada llamada lo escribe literal en la
 * plantilla (`.../ruta?${query(...)}`) porque `lib/contrato.test.ts`
 * escanea el código fuente y corta la ruta en el primer `?` — si el `?`
 * viviera acá adentro, la ruta que el escaneo ve sería la llamada a
 * `query(...)` entera, no la ruta real. */
function query(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params)) {
    if (valor !== undefined) q.set(clave, String(valor));
  }
  return q.toString();
}

export const apiDelivery = {
  misRutas: () => pedir<RutaConParadas[]>("/delivery/mi/rutas"),

  iniciarRuta: (rutaId: string) =>
    pedir<RutaAck>(`/delivery/rutas/${rutaId}/iniciar`, { metodo: "POST" }),

  finalizarRuta: (rutaId: string) =>
    pedir<RutaAck>(`/delivery/rutas/${rutaId}/finalizar`, { metodo: "POST" }),

  registrarPosicion: (rutaId: string, cuerpo: PosicionEnvio) =>
    pedir<void>(`/delivery/rutas/${rutaId}/posiciones`, { metodo: "POST", cuerpo }),

  entregar: (entregaId: string, cuerpo: EntregarEnvio) =>
    pedir<EntregaAck>(`/delivery/entregas/${entregaId}/entregar`, {
      metodo: "POST",
      cuerpo,
    }),

  fallar: (entregaId: string, cuerpo: FallarEnvio) =>
    pedir<EntregaAck>(`/delivery/entregas/${entregaId}/fallar`, {
      metodo: "POST",
      cuerpo,
    }),

  // --- Tablero de despacho -----------------------------------------------------
  tablero: (sucursalId: string, fecha?: string) =>
    pedir<Tablero>(`/delivery/tablero?${query({ sucursal_id: sucursalId, fecha })}`),

  crearRuta: (cuerpo: RutaEnvio) => pedir<RutaAck>("/delivery/rutas", { metodo: "POST", cuerpo }),

  cancelarRuta: (rutaId: string) =>
    pedir<RutaAck>(`/delivery/rutas/${rutaId}/cancelar`, { metodo: "POST" }),

  editarParadas: (rutaId: string, cuerpo: { venta_ids: string[]; optimizar?: boolean }) =>
    pedir<RutaAck>(`/delivery/rutas/${rutaId}/paradas`, { metodo: "PUT", cuerpo }),

  candidatosRepartidor: (empresaId: string) =>
    pedir<RepartidorCandidato[]>(
      `/delivery/repartidores/candidatos?${query({ empresa_id: empresaId })}`,
    ),

  repartidores: (sucursalId?: string, activo?: boolean) =>
    pedir<Repartidor[]>(
      `/delivery/repartidores?${query({ sucursal_id: sucursalId, activo })}`,
    ),

  crearRepartidor: (cuerpo: RepartidorEnvio) =>
    pedir<Repartidor>("/delivery/repartidores", { metodo: "POST", cuerpo }),

  editarRepartidor: (repartidorId: string, cambios: RepartidorCambios) =>
    pedir<Repartidor>(`/delivery/repartidores/${repartidorId}`, {
      metodo: "PATCH",
      cuerpo: cambios,
    }),

  entregas: (params: {
    sucursal_id?: string;
    desde?: string;
    hasta?: string;
    estado?: string;
    repartidor_id?: string;
    page?: number;
    page_size?: number;
  }) => pedir<Pagina<EntregaHistorial>>(`/delivery/entregas?${query(params)}`),
};
