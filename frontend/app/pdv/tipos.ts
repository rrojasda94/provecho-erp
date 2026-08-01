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
};

export const totalLinea = (l: LineaBorrador): number =>
  l.cantidad * l.precio +
  l.extras.reduce((a, e) => a + e.precio * e.cantidad * l.cantidad, 0);

export const totalBorrador = (b: Borrador): number =>
  b.lineas.reduce((a, l) => a + totalLinea(l), 0);

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
