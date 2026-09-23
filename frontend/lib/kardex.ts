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

type Ritmo = {
  stock: string;
  stock_minimo: string | null;
  consumo_diario: string | null;
  /** En una sede o un almacén es la próxima reposición, no una compra. */
  proxima_compra: string | null;
  reposiciones_90_dias: number;
};

export type Kardex = Ritmo & { articulo_id: string; semanas: SemanaKardex[] };

/** Una fila de «cómo está cada sede». */
export type KardexAlmacen = Ritmo & {
  almacen_id: string;
  almacen: string;
  sucursal_id: string | null;
  sucursal: string | null;
};

/** Dónde se mira el kardex. `null` es la empresa entera. */
export type Ambito = { tipo: "almacen" | "sucursal"; id: string } | null;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** `?ambito=almacen:<id>` o `sucursal:<id>`. Lo que no se entiende es la
 * empresa: la URL la escribe cualquiera. */
export function leerAmbito(param: string | undefined): Ambito {
  const [tipo, id] = (param ?? "").split(":");
  if ((tipo === "almacen" || tipo === "sucursal") && UUID.test(id ?? ""))
    return { tipo, id };
  return null;
}

/** El query del kardex para ese ámbito (`almacen_id=` o `sucursal_id=`),
 * sin el `?`: vacío es la empresa. */
export function queryDeAmbito(ambito: Ambito): string {
  return ambito ? `${ambito.tipo}_id=${ambito.id}` : "";
}

/** Cómo marcar una sede en la tabla: bajo el mínimo es peligro; reponer en
 * una semana o menos, alerta. */
export function estadoDeSede(
  fila: KardexAlmacen,
  hoy: string,
): "peligro" | "alerta" | null {
  if (
    fila.stock_minimo !== null &&
    Number(fila.stock) <= Number(fila.stock_minimo)
  ) {
    return "peligro";
  }
  if (fila.proxima_compra !== null && diasHasta(fila.proxima_compra, hoy) <= 7)
    return "alerta";
  return null;
}

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
