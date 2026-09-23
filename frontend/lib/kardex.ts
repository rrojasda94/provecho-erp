/**
 * Kardex gráfico de un artículo (ficha en Inventario y en Compras). Tipos del
 * contrato y las cuentas que la pantalla hace sobre ellos: sin React, para
 * poder probarlas con `node --test`.
 */

export type SemanaKardex = {
  semana: string;
  entradas: string;
  salidas: string;
  saldo: string;
};

export type Kardex = {
  articulo_id: string;
  stock: string;
  stock_minimo: string | null;
  consumo_diario: string | null;
  proxima_compra: string | null;
  semanas: SemanaKardex[];
};

export type PrecioHistorico = {
  fecha: string;
  costo_unitario: string;
  cantidad: string;
  orden_compra_id: string;
  proveedor_id: string;
  proveedor: string | null;
};

const DIA_MS = 86_400_000;

/** Cada cuántos días se compra, en promedio, entre días de recepción
 * distintos. `null` con menos de dos compras: no hay intervalo que medir. */
export function frecuenciaCompra(fechas: string[]): number | null {
  const dias = [...new Set(fechas.map((f) => f.slice(0, 10)))].sort();
  if (dias.length < 2) return null;
  const total = Date.parse(dias.at(-1)!) - Date.parse(dias[0]);
  return Math.round(total / DIA_MS / (dias.length - 1));
}

/** Días desde `hoy` hasta `fecha` (ambas `YYYY-MM-DD`). Negativo si pasó. */
export function diasHasta(fecha: string, hoy: string): number {
  return Math.round((Date.parse(fecha) - Date.parse(hoy)) / DIA_MS);
}

/** Cuánto cambió el último precio contra el anterior, en %. */
export function variacionPrecio(precios: PrecioHistorico[]): number | null {
  if (precios.length < 2) return null;
  const ultimo = Number(precios.at(-1)!.costo_unitario);
  const previo = Number(precios.at(-2)!.costo_unitario);
  return previo > 0
    ? Math.round(((ultimo - previo) / previo) * 1000) / 10
    : null;
}
