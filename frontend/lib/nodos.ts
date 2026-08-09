/**
 * Fusión de recetas por nodos: qué lleva realmente un plato configurado.
 *
 * Un producto comercial no tiene una receta, tiene un **camino**: tamaño →
 * combinación (sabor) → extras → restas (RN-PRD-004), y encima el empaque
 * según la modalidad (RN-EMP-003). Cada tramo aporta su propia receta y el
 * plato es la suma. Este archivo hace esa suma y nada más: no habla con la
 * API, no sabe de React, y por eso se puede probar solo (`nodos.test.ts`).
 *
 * **Es una simulación, no la fuente de la verdad.** Lo que se descuenta del
 * almacén lo calcula el servidor al confirmar la venta
 * (`inventory.listeners`), con Decimal y con la merma de cada línea. Acá se
 * usa aritmética de punto flotante a propósito: el número se muestra y se
 * descarta, no se guarda ni se cobra. Si alguna vez este resultado se
 * persistiera, tendría que salir del servidor.
 */

import type { RecetaDetalle } from "@/lib/catalogo";

/** Un tramo del camino: de dónde sale la receta que aporta. */
export type ParteDeReceta = {
  /** "Familiar", "Peperoni", "Extra queso" — lo que el usuario reconoce. */
  titulo: string;
  tipo: "tamano" | "sabor" | "extra";
  receta: RecetaDetalle | null;
  /** Porciones del extra en la línea (2 = doble queso). Base y sabor: 1. */
  veces?: number;
};

export type LineaFusionada = {
  articuloId: string;
  articulo: string;
  unidad: string;
  cantidad: number;
  costo: number;
  /** Todos los tramos que aportan este insumo: "Familiar + Extra queso". */
  origen: string;
  /** El insumo está en la receta pero el plato lo quita ("sin cebolla"). */
  quitado: boolean;
};

export type Fusion = {
  lineas: LineaFusionada[];
  /** Costo de lo que sí se prepara. Las restas no cuentan. */
  costo: number;
  /** Lo que se ahorra por las restas. Informativo: no baja el precio. */
  costoQuitado: number;
  /** Insumos que la receta pone y se pueden quitar, en orden de nombre. */
  quitables: { articuloId: string; articulo: string }[];
};

/**
 * Una receta rinde N porciones; el plato lleva una. `costo_linea` y
 * `cantidad` vienen por el rendimiento completo, así que todo se divide.
 * Es el mismo criterio de `inventory.queries_publicas.costo_unitario_de_recetas`
 * — si acá se dividiera distinto, dos pantallas del ERP mostrarían números
 * distintos para el mismo plato.
 */
function rendimiento(receta: RecetaDetalle): number {
  const n = Number(receta.rendimiento_cantidad);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

export function fusionar(
  partes: ParteDeReceta[],
  sinArticuloIds: string[] = [],
): Fusion {
  const sin = new Set(sinArticuloIds);
  const porArticulo = new Map<string, LineaFusionada>();

  for (const parte of partes) {
    if (!parte.receta) continue;
    const porPlato = rendimiento(parte.receta);
    const veces = parte.veces ?? 1;
    for (const item of parte.receta.items) {
      const cantidad = (Number(item.cantidad) / porPlato) * veces;
      const costo = (Number(item.costo_linea) / porPlato) * veces;
      const previa = porArticulo.get(item.articulo_id);
      if (previa) {
        // El mismo insumo desde dos tramos se suma en una línea: cocina
        // pesa el queso una vez, no dos. El origen conserva de dónde salió
        // cada aporte para que se entienda el total.
        previa.cantidad += cantidad;
        previa.costo += costo;
        if (!previa.origen.includes(parte.titulo)) {
          previa.origen += ` + ${parte.titulo}`;
        }
      } else {
        porArticulo.set(item.articulo_id, {
          articuloId: item.articulo_id,
          articulo: item.articulo_nombre,
          unidad: item.unidad_medida_nombre,
          cantidad,
          costo,
          origen: parte.titulo,
          quitado: sin.has(item.articulo_id),
        });
      }
    }
  }

  const lineas = [...porArticulo.values()].sort((a, b) =>
    a.articulo.localeCompare(b.articulo, "es"),
  );
  return {
    lineas,
    costo: lineas.filter((l) => !l.quitado).reduce((t, l) => t + l.costo, 0),
    costoQuitado: lineas.filter((l) => l.quitado).reduce((t, l) => t + l.costo, 0),
    quitables: lineas.map((l) => ({
      articuloId: l.articuloId,
      articulo: l.articulo,
    })),
  };
}

/** Margen de contribución de la combinación: lo que deja el plato. */
export function margen(precio: number, costo: number) {
  return {
    monto: precio - costo,
    /** null y no 0 cuando no hay precio: "sin precio" no es "0 %". */
    pct: precio > 0 ? ((precio - costo) / precio) * 100 : null,
  };
}

export function soles(valor: number): string {
  return `S/ ${valor.toFixed(2)}`;
}

/** 0.5 → "0.5", 180 → "180". Sin ceros de relleno, igual que el servidor. */
export function cantidadCorta(valor: number): string {
  return Number(valor.toFixed(4)).toString();
}
