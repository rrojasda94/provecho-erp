import type { ClienteBuscado } from "@/lib/pdv";

/** Extra agregado a una línea. Es una línea propia en el backend
 * (RN-COM-021), pero en el ticket se dibuja bajo su plato. */
export type ExtraEnLinea = {
  productoId: string;
  nombre: string;
  precio: number;
  cantidad: number;
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
 * creer que hay algo que cobrar (RN-COM-025). */
export const totalBorrador = (b: Borrador): number =>
  esConsumoPersonal(b) ? 0 : b.lineas.reduce((a, l) => a + totalLinea(l), 0);

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
