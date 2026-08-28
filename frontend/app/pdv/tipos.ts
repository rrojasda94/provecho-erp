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
  /**
   * `false` mientras la línea solo existe en esta pantalla (ADR-075).
   *
   * Marcar un producto sobre una mesa ya abierta **no** lo manda a cocina:
   * queda pendiente hasta que el trabajador confirma con "Enviar aumento",
   * y recién entonces sale como una comanda nueva. Antes la línea viajaba
   * al confirmar el diálogo del producto y aparecía al instante dentro de
   * la pastilla del pedido original, así que el cocinero no distinguía lo
   * que acababa de entrar de lo que llevaba media hora esperando.
   */
  enviada: boolean;
};

/**
 * Un pedido en curso. La `venta` en la base nace recién al enviarlo a cocina
 * o cobrarlo (RN-COM-005), así que el cajero puede tener varios abiertos a
 * la vez sin ensuciar nada.
 *
 * Desde ADR-074 el borrador **también se guarda en el servidor**, contra el
 * punto de venta. No lo convierte en una venta: sigue sin descontar stock,
 * sin asentar y sin número de orden. Lo que cambia es que recargar la
 * página, quedarse sin batería o cambiar de turno ya no lo borra.
 */
export type Borrador = {
  id: string;
  tipo: "mesa" | "takeout" | "delivery" | null;
  mesaId: string | null;
  mesaNumero: number | null;
  comensales: number | null;
  /** Cómo se sirve el pedido entero: "servir todo junto", "bebidas al
   * final". Del pedido y no de una línea — esa es `LineaBorrador.nota`. */
  notaCocina: string;
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
  /** Descuento manual ya aplicado sobre la orden (RN-COM-017). Lo resuelve
   * el servidor; acá vive para poder mostrar el total real antes de cobrar
   * y para no ofrecer un cupón encima (RN-PRM-006). */
  descuento: { modo: "porcentaje" | "monto"; valor: number; motivo: string } | null;
  /** Código del cupón canjeado, o `null`. Mismo motivo. */
  cupon: string | null;
  /**
   * Las promociones que el pedido activó solo (ADR-076).
   *
   * Las resuelve el servidor y acá viven **para poder mostrarlas**: si el
   * cajero no puede decir de dónde salió el descuento, la promoción está mal
   * nombrada — pero callarla es peor, porque el cliente ve un total que no
   * cuadra con la carta.
   */
  promociones: { nombre: string; monto: number }[];
};

/** A dónde van los productos seleccionados al "mover productos" (RN-COM-043):
 * otra orden ya abierta, o una mesa libre. Ninguno de los dos = separar la
 * cuenta dentro de la misma orden ("cobrar seleccionados"), que no pasa por
 * este diálogo. */
export type DestinoMover = { ventaId: string } | { mesaId: string };

/**
 * Motivos de descuento manual que el servidor acepta
 * (`sales.domain.rules.MOTIVOS_DESCUENTO`), no texto libre.
 *
 * Es un catálogo cerrado porque el dato existe para **agrupar** el margen
 * regalado por causa, y un campo abierto no agrupa: "cliente frecuente",
 * "cte frecuente" y "frecuente" son tres motivos distintos para el reporte y
 * el mismo para quien lo tecleó. Que la lista de acá coincida con la del
 * backend lo vigila `tests/test_repo_coherencia.py`.
 *
 * `cupon` no está: ese motivo lo pone el canje del cupón, no una persona.
 */
export const MOTIVOS_DESCUENTO = [
  ["cortesia", "Cortesía"],
  ["reclamo", "Reclamo"],
  ["colaborador", "Colaborador"],
  ["promocion", "Promoción"],
  ["convenio", "Convenio"],
] as const;

/** La clave que guarda el servidor, en el idioma de la caja. */
export const etiquetaMotivoDescuento = (motivo: string): string =>
  MOTIVOS_DESCUENTO.find(([clave]) => clave === motivo)?.[1] ?? motivo;

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
/** Lo que las promociones automáticas le bajan al pedido. */
export const promocionesDeBorrador = (b: Borrador): number =>
  b.promociones.reduce((a, p) => a + p.monto, 0);

/** Lo que el descuento manual le baja al pedido (RN-COM-017).
 *
 * Se calcula sobre los productos y **no** sobre el reparto: el flete no es
 * margen del local, es lo que cuesta llevarlo. Es el mismo criterio del
 * servidor, que es quien manda — esto solo evita que el cajero cante un
 * total y la caja cobre otro. */
export const descuentoDeBorrador = (b: Borrador): number => {
  if (!b.descuento) return 0;
  // Sobre lo ya promocionado, igual que el servidor (ADR-076): el supervisor
  // firma un porcentaje de lo que el cliente va a pagar, no del precio de
  // lista de algo que la promoción ya rebajó.
  const productos =
    b.lineas.reduce((a, l) => a + totalLinea(l), 0) - promocionesDeBorrador(b);
  return b.descuento.modo === "porcentaje"
    ? (productos * b.descuento.valor) / 100
    : Math.min(b.descuento.valor, productos);
};

export const totalBorrador = (b: Borrador): number =>
  esConsumoPersonal(b)
    ? 0
    : b.lineas.reduce((a, l) => a + totalLinea(l), 0) +
      (b.costoEntrega ?? 0) -
      promocionesDeBorrador(b) -
      descuentoDeBorrador(b);

/** Lo que todavía no salió a cocina. En un pedido nuevo son todas sus
 * líneas; en uno ya enviado, el aumento que espera confirmación. */
export const lineasPendientes = (b: Borrador): LineaBorrador[] =>
  b.lineas.filter((l) => !l.enviada);

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
