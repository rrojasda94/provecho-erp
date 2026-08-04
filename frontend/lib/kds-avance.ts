/**
 * Máquina de estados del avance de cocina, sin dependencias — espeja
 * `sales.domain.rules.ORDEN_PREPARACION`. Vive aparte del cliente HTTP
 * (`lib/kds.ts`) por dos razones: es la única lógica del KDS que puede
 * equivocarse en silencio, y así se prueba con `node --test` sin arrastrar
 * `fetch` ni sumar un framework de tests.
 */

export type EstadoItem = "pendiente" | "en_preparacion" | "listo" | "entregado";

/** Secuencia estricta, sin retroceso (RN-CUP-002). `entregado` no se alcanza
 * desde cocina: lo cierra `POST /sales/ventas/{id}/entrega` (RN-CUP-006). */
export const ORDEN: EstadoItem[] = [
  "pendiente",
  "en_preparacion",
  "listo",
  "entregado",
];

/** Pasos que faltan para llevar un ítem hasta `listo` — uno por request,
 * porque la API solo acepta el estado inmediatamente siguiente. Vacío si ya
 * está listo o entregado. */
export function pasosHastaListo(desde: EstadoItem): EstadoItem[] {
  return ORDEN.slice(ORDEN.indexOf(desde) + 1, ORDEN.indexOf("listo") + 1);
}

export const ETIQUETA_ESTADO: Record<EstadoItem, string> = {
  pendiente: "Pendiente",
  en_preparacion: "En preparación",
  listo: "Listo",
  entregado: "Entregado",
};
