/**
 * A qué pantalla lleva un reporte (ADR-036).
 *
 * El backend (`src/core/destinos.py`) dice a qué **endpoint** apunta cada
 * `referencia_tipo` y con qué permiso; acá se traduce a la ruta de la app.
 * La traducción vive del lado del cliente porque el backend no conoce el
 * router de Next.js, y el permiso no se duplica: viaja en `destinos` de
 * `GET /reports/emisiones` y se consulta con `tienePermiso`.
 *
 * Un tipo sin entrada acá devuelve `null` y la ficha no dibuja el botón. Es
 * preferible a un enlace que lleva a una pantalla que no existe: eso vuelve
 * a dejar al reporte como una línea de texto, que es de donde venimos.
 */

/** `referencia_tipo` → ruta de la app, con el id ya interpolado. */
const RUTAS: Record<string, (id: string) => string> = {
  venta: (id) => `/ventas/${id}`,
  // El SKU se mira en la ficha de su artículo: es donde está el stock por
  // almacén, que es lo que hay que ver para decidir reponer.
  sku: (id) => `/inventario/skus/${id}`,
  articulo: (id) => `/inventario/articulos/${id}`,
  lote: (id) => `/inventario/lotes?lote=${id}`,
  categoria: (id) => `/inventario/categorias?categoria=${id}`,
  devolucion: (id) => `/inventario/devoluciones?devolucion=${id}`,
  ajuste: (id) => `/inventario/ajustes?ajuste=${id}`,
  cierre_caja: (id) => `/contabilidad/caja?cierre=${id}`,
  movimiento_dinero: (id) => `/contabilidad/pagos?pago=${id}`,
  orden_produccion: (id) => `/produccion?orden=${id}`,
  escalamiento: (id) => `/reportes/escalamientos/${id}`,
};

export function rutaDestino(
  tipo: string | null | undefined,
  id: string | null | undefined,
): string | null {
  if (!tipo || !id) return null;
  return RUTAS[tipo]?.(id) ?? null;
}

/** Rótulo del botón. El backend manda el suyo en `GET /reports/emisiones`;
 * este es el respaldo para cuando esa llamada no se hizo (o dio 403). */
const ETIQUETAS: Record<string, string> = {
  venta: "Ver la venta",
  sku: "Ver el stock",
  articulo: "Ver el artículo",
  lote: "Ver el lote",
  categoria: "Ver la categoría",
  devolucion: "Ver la devolución",
  ajuste: "Revisar el ajuste",
  cierre_caja: "Ver el cierre de caja",
  movimiento_dinero: "Ver el pago",
  orden_produccion: "Ver la orden",
  escalamiento: "Ver el escalamiento",
};

export function etiquetaDestino(tipo: string | null | undefined): string {
  return (tipo && ETIQUETAS[tipo]) || "Ver el detalle";
}

/**
 * Sube al tope la fila que vino del reporte.
 *
 * Aterrizar en una lista y tener que buscar la fila a mano es la mitad del
 * problema que el enlace vino a resolver. Ordenar en vez de filtrar es
 * deliberado: el contexto de alrededor —qué más hay pendiente en ese
 * almacén, en esa caja— suele ser parte de la decisión.
 */
export function primeroElDe<T>(
  items: T[],
  id: string | null,
  clave: (item: T) => string,
): T[] {
  if (!id) return items;
  return [...items].sort((a, b) =>
    clave(a) === id ? -1 : clave(b) === id ? 1 : 0,
  );
}
