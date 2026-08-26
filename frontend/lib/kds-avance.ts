/**
 * Máquina de estados del avance de cocina, sin dependencias — espeja
 * `sales.domain.rules.ORDEN_PREPARACION`. Vive aparte del cliente HTTP
 * (`lib/kds.ts`) por dos razones: es la única lógica del KDS que puede
 * equivocarse en silencio, y así se prueba con `node --test` sin arrastrar
 * `fetch` ni sumar un framework de tests.
 */

export type EstadoItem = "pendiente" | "en_preparacion" | "listo" | "entregado";

/** Secuencia estricta, de a un paso (RN-CUP-002). `entregado` no se alcanza
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

/**
 * A qué estado lleva **un** toque sobre la línea (2026-08-26).
 *
 * Antes un toque encadenaba `pendiente → en_preparacion → listo` y mandaba la
 * línea a la estación siguiente de una: el roce accidental de un delantal
 * despachaba el plato. Ahora hacen falta dos toques —el primero dice "lo
 * estoy haciendo", el segundo "sale"— y el error necesita dos.
 *
 * `null` = no queda nada que tocar en esta pantalla.
 */
export function siguienteToque(desde: EstadoItem): EstadoItem | null {
  const proximo = ORDEN[ORDEN.indexOf(desde) + 1];
  return proximo && proximo !== "entregado" ? proximo : null;
}

export const ETIQUETA_ESTADO: Record<EstadoItem, string> = {
  pendiente: "Pendiente",
  en_preparacion: "En preparación",
  listo: "Listo",
  entregado: "Entregado",
};
