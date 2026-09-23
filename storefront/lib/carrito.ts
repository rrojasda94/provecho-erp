"use client";

/**
 * Carrito del sitio (ADR-105): vive en `localStorage`, nunca en el servidor
 * hasta que se confirma el pedido — el precio que se ve acá es solo para
 * mostrar, `sales` lo vuelve a fijar server-side al confirmar (RN-PRC-003).
 *
 * Una línea es un producto/tamaño + lo que se le eligió (extras y sabores de la
 * Mitad x Mitad) + una cantidad. La misma pizza con otros sabores es **otra
 * línea**: se distingue por `clave`.
 */

export type ExtraEnLinea = { id: string; nombre: string; precio: string; cantidad: number };
export type ValorEnLinea = { id: string; nombre: string; atributo: string };

export type LineaCarrito = {
  /** Identifica la línea: producto + sabores + extras elegidos. */
  clave: string;
  productoComercialId: string;
  nombre: string;
  /** Precio de UNA unidad con el recargo de los sabores, sin los extras. */
  precio: string;
  fotoUrl: string | null;
  cantidad: number;
  extras: ExtraEnLinea[];
  valores: ValorEnLinea[];
};

const CLAVE = "charlies_carrito";
const EVENTO = "charlies:carrito";

export function claveDeLinea(
  productoComercialId: string,
  valores: ValorEnLinea[],
  extras: ExtraEnLinea[],
): string {
  const v = valores.map((x) => x.id).sort().join(",");
  const e = extras.map((x) => `${x.id}:${x.cantidad}`).sort().join(",");
  return `${productoComercialId}|${v}|${e}`;
}

/** Los carritos guardados antes de las opciones no traen `clave`, `extras` ni
 * `valores`: se completan para que sigan leyéndose. */
function normalizar(l: Partial<LineaCarrito> & { productoComercialId: string }): LineaCarrito {
  return {
    clave: l.clave ?? l.productoComercialId,
    productoComercialId: l.productoComercialId,
    nombre: l.nombre ?? "",
    precio: l.precio ?? "0",
    fotoUrl: l.fotoUrl ?? null,
    cantidad: l.cantidad ?? 1,
    extras: l.extras ?? [],
    valores: l.valores ?? [],
  };
}

function leer(): LineaCarrito[] {
  try {
    const crudo = window.localStorage.getItem(CLAVE);
    return crudo ? (JSON.parse(crudo) as LineaCarrito[]).map(normalizar) : [];
  } catch {
    return [];
  }
}

function guardar(lineas: LineaCarrito[]): void {
  try {
    window.localStorage.setItem(CLAVE, JSON.stringify(lineas));
    window.dispatchEvent(new Event(EVENTO));
  } catch {
    // Storage bloqueado (privado, cuota) — el carrito no persiste, pero la
    // página no se rompe.
  }
}

export function obtenerCarrito(): LineaCarrito[] {
  if (typeof window === "undefined") return [];
  return leer();
}

export function agregarAlCarrito(
  item: Omit<LineaCarrito, "cantidad" | "clave" | "extras" | "valores"> &
    Partial<Pick<LineaCarrito, "extras" | "valores">>,
  cantidad = 1,
): LineaCarrito[] {
  const extras = item.extras ?? [];
  const valores = item.valores ?? [];
  const clave = claveDeLinea(item.productoComercialId, valores, extras);
  const lineas = leer();
  const existente = lineas.find((l) => l.clave === clave);
  if (existente) {
    existente.cantidad = Math.min(existente.cantidad + cantidad, 20);
  } else {
    lineas.push({ ...item, clave, extras, valores, cantidad: Math.min(cantidad, 20) });
  }
  guardar(lineas);
  return lineas;
}

export function actualizarCantidad(clave: string, cantidad: number): LineaCarrito[] {
  const lineas = leer();
  const siguiente =
    cantidad <= 0
      ? lineas.filter((l) => l.clave !== clave)
      : lineas.map((l) => (l.clave === clave ? { ...l, cantidad } : l));
  guardar(siguiente);
  return siguiente;
}

export function quitarDelCarrito(clave: string): LineaCarrito[] {
  return actualizarCantidad(clave, 0);
}

export function vaciarCarrito(): void {
  guardar([]);
}

/** Precio de UNA unidad de la línea: el producto con sus sabores más los extras
 * (cada extra por su cantidad). */
export function precioDeLinea(l: LineaCarrito): number {
  return Number(l.precio) + l.extras.reduce((acc, e) => acc + Number(e.precio) * e.cantidad, 0);
}

export function totalDelCarrito(lineas: LineaCarrito[]): number {
  return lineas.reduce((acc, l) => acc + precioDeLinea(l) * l.cantidad, 0);
}

export function cantidadTotal(lineas: LineaCarrito[]): number {
  return lineas.reduce((acc, l) => acc + l.cantidad, 0);
}

/** Se suscribe a cambios del carrito (mismo tab vía evento propio, otras
 * tabs vía `storage`). Devuelve la función para desuscribirse. */
export function alCambiarCarrito(cb: () => void): () => void {
  const manejador = () => cb();
  window.addEventListener(EVENTO, manejador);
  window.addEventListener("storage", manejador);
  return () => {
    window.removeEventListener(EVENTO, manejador);
    window.removeEventListener("storage", manejador);
  };
}
