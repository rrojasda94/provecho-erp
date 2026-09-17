"use client";

/**
 * Carrito del sitio (ADR-103): vive en `localStorage`, nunca en el servidor
 * hasta que se confirma el pedido — el precio que se ve acá es solo para
 * mostrar, `sales` lo vuelve a fijar server-side al confirmar (RN-PRC-003).
 *
 * Simplificación de este slice: una línea es un producto/tamaño + cantidad,
 * sin extras ni Mitad x Mitad (ver `docs/roadmap/deuda/modulo-storefront.md`).
 */

export type LineaCarrito = {
  productoComercialId: string;
  nombre: string;
  precio: string;
  fotoUrl: string | null;
  cantidad: number;
};

const CLAVE = "charlies_carrito";
const EVENTO = "charlies:carrito";

function leer(): LineaCarrito[] {
  try {
    const crudo = window.localStorage.getItem(CLAVE);
    return crudo ? (JSON.parse(crudo) as LineaCarrito[]) : [];
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
  item: Omit<LineaCarrito, "cantidad">,
  cantidad = 1,
): LineaCarrito[] {
  const lineas = leer();
  const existente = lineas.find((l) => l.productoComercialId === item.productoComercialId);
  if (existente) {
    existente.cantidad = Math.min(existente.cantidad + cantidad, 20);
  } else {
    lineas.push({ ...item, cantidad: Math.min(cantidad, 20) });
  }
  guardar(lineas);
  return lineas;
}

export function actualizarCantidad(productoComercialId: string, cantidad: number): LineaCarrito[] {
  const lineas = leer();
  const siguiente =
    cantidad <= 0
      ? lineas.filter((l) => l.productoComercialId !== productoComercialId)
      : lineas.map((l) =>
          l.productoComercialId === productoComercialId ? { ...l, cantidad } : l,
        );
  guardar(siguiente);
  return siguiente;
}

export function quitarDelCarrito(productoComercialId: string): LineaCarrito[] {
  return actualizarCantidad(productoComercialId, 0);
}

export function vaciarCarrito(): void {
  guardar([]);
}

export function totalDelCarrito(lineas: LineaCarrito[]): number {
  return lineas.reduce((acc, l) => acc + Number(l.precio) * l.cantidad, 0);
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
