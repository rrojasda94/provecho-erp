import type { Ubicacion } from "@/components/direccion/ubicacion";
import type { ClienteBuscado } from "@/lib/pdv";

/** Extra agregado a una línea. Es una línea propia en el backend
 * (RN-COM-021), pero en el ticket se dibuja bajo su plato. */
export type ExtraEnLinea = {
  productoId: string;
  nombre: string;
  precio: number;
  cantidad: number;
};

/** Insumo que la línea quita ("sin cebolla"). Se guarda el nombre además
 * del id para poder dibujar el ticket sin volver a preguntar. */
export type RestaEnLinea = {
  articuloId: string;
  nombre: string;
};

/** Un valor de atributo elegido en la línea: qué mitad lleva qué.
 *
 * Guarda el nombre además del id —igual que `RestaEnLinea`— para poder
 * dibujar el ticket sin volver a buscar en la carta. `precioExtra` ya está
 * sumado en `LineaBorrador.precio`; viaja para poder mostrarlo desglosado. */
export type ValorEnLinea = {
  ptavId: string;
  atributoId: string;
  nombre: string;
  precioExtra: number;
};

export type LineaBorrador = {
  /** Identificador local: la línea no existe en la base hasta enviar. */
  id: string;
  productoId: string;
  nombre: string;
  precio: number;
  cantidad: number;
  nota: string;
  extras: ExtraEnLinea[];
  /** Restas: no tocan el total —quitar cebolla no abarata la pizza— pero sí
   * el descuento de inventario (RN-PRD-004). Por eso no entran en
   * `totalLinea`. */
  restas: RestaEnLinea[];
  /** Qué se eligió en cada atributo (los sabores de la mitad-y-mitad). A
   * diferencia de las restas, esto sí puede mover el total: el recargo del
   * valor ya viene sumado en `precio` (RN-COM-036). */
  valores: ValorEnLinea[];
  grupoCobro: number;
};

/**
 * Un pedido en curso. **Vive solo en el PDV** hasta que se envía a cocina o
 * se cobra: recién ahí nace la `venta` en la base (RN-COM-005). Por eso el
 * cajero puede tener varios abiertos a la vez sin ensuciar nada.
 */
export type Borrador = {
  id: string;
  tipo: "mesa" | "takeout" | "delivery" | null;
  mesaId: string | null;
  mesaNumero: number | null;
  comensales: number | null;
  direccion: string | null;
  /** Lo que sale el reparto, cotizado por el servidor al anclar la dirección
   * (ADR-054). `null` = todavía no se cotizó o el pedido no se lleva. Es
   * informativo: el monto que se cobra lo recalcula la API al crear la venta,
   * y es el que queda congelado en la fila. */
  costoEntrega: number | null;
  /** El punto en el mapa de esa dirección, cuando se eligió con el
   * buscador. Sin él el pedido se toma igual y el reparto se cobra a
   * tarifa base (ADR-054). */
  ubicacion: Ubicacion;
  cliente: ClienteBuscado | null;
  lineas: LineaBorrador[];
  /** Se llena al enviar: desde ese momento el pedido existe en la base. */
  ventaId: string | null;
  numeroOrden: number | null;
  hora: string;
  /** Comida del personal (RN-COM-025): el pedido vale cero, no se cobra y su
   * costo va a gasto. Se marca antes de enviar, con PIN del encargado. */
  consumoMotivo: string | null;
  consumoAutorizacion: string | null;
};

/** A dónde van los productos seleccionados al "mover productos" (RN-COM-043):
 * otra orden ya abierta, o una mesa libre. Ninguno de los dos = separar la
 * cuenta dentro de la misma orden ("cobrar seleccionados"), que no pasa por
 * este diálogo. */
export type DestinoMover = { ventaId: string } | { mesaId: string };

/** Motivos de consumo de personal, como los nombra el backend. */
export const MOTIVOS_CONSUMO: { valor: string; etiqueta: string }[] = [
  { valor: "fin_semana", etiqueta: "Fin de semana" },
  { valor: "feriado", etiqueta: "Feriado" },
  { valor: "alta_actividad", etiqueta: "Día de alta actividad" },
  { valor: "capacitacion", etiqueta: "Capacitación" },
  { valor: "otro", etiqueta: "Otro" },
];

export const esConsumoPersonal = (b: Borrador): boolean =>
  b.consumoMotivo !== null;

export const totalLinea = (l: LineaBorrador): number =>
  l.cantidad * l.precio +
  l.extras.reduce((a, e) => a + e.precio * e.cantidad * l.cantidad, 0);

/** El consumo de personal no tiene precio: mostrar el de la carta haría
 * creer que hay algo que cobrar (RN-COM-025).
 *
 * El reparto suma al final y no por línea (RN-COM-041): es del pedido, no de
 * lo que se comió. El número que manda es el que recalcula el servidor —esto
 * es lo que el cajero le dice al cliente antes de cobrar. */
export const totalBorrador = (b: Borrador): number =>
  esConsumoPersonal(b)
    ? 0
    : b.lineas.reduce((a, l) => a + totalLinea(l), 0) + (b.costoEntrega ?? 0);

export const etiquetaTipo = (b: Borrador): string => {
  if (b.tipo === "mesa") return `Mesa ${b.mesaNumero ?? "?"}`;
  if (b.tipo === "takeout") return "Para llevar";
  if (b.tipo === "delivery") return "Delivery";
  return "Sin tipo";
};

/** Qué le falta al pedido para poder salir. Cobrar es enviar + cobrar, así
 * que ambos exigen lo mismo. */
export function faltaEnBorrador(b: Borrador): string | null {
  if (!b.tipo) return "Elige el tipo de orden";
  if (b.tipo === "mesa" && !b.mesaId) return "Indica el número de mesa";
  if (b.tipo === "delivery" && !b.direccion) {
    return "El delivery necesita dirección de entrega";
  }
  return null;
}
