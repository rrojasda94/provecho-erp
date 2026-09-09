/**
 * Cliente y tipos de la PWA del repartidor (ADR-098). Espeja
 * `src/modules/delivery/api/schemas.py` — solo lo que `GET /delivery/mi/rutas`
 * y las acciones de una entrega necesitan, no el módulo entero (eso es del
 * tablero de despacho, que vive en el shell y no acá).
 */

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

export const ETIQUETA_MOTIVO: Record<MotivoFallo, string> = {
  cliente_ausente: "El cliente no estaba",
  direccion_errada: "La dirección está mal",
  rechazo: "El cliente lo rechazó",
  no_contesta: "No contesta el teléfono ni el timbre",
  otro: "Otro motivo",
};

export type MiParada = {
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
};

export type MiRuta = {
  id: string;
  sucursal_id: string;
  estado: EstadoRuta;
  hora_salida: string | null;
  origen_lat: string | number;
  origen_lng: string | number;
  distancia_m: number | null;
  duracion_seg: number | null;
  ultima_lat: string | number | null;
  ultima_lng: string | number | null;
  ultima_posicion_at: string | null;
  paradas: MiParada[];
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

type RutaAck = { id: string; estado: EstadoRuta };
type EntregaAck = { id: string; estado: EstadoEntrega };

export const apiDelivery = {
  misRutas: () => pedir<MiRuta[]>("/delivery/mi/rutas"),

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
};
