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

import type { Articulo, RecetaDetalle, RecetaItem } from "@/lib/catalogo";
// Relativo y con extensión: `nodos.ts` corre bajo `node --test`, que no
// resuelve el alias `@/` (los `import type` sí, porque TypeScript los borra).
import { firmaDeCondicion } from "./matriz.ts";

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

/**
 * Prefijo de grupo para un PTAV sin atributo conocido — mismo criterio que
 * `_GRUPO_HUERFANO` en `inventory/domain/rules.py`: un caracter que un id de
 * atributo real nunca produce, para que el grupo huérfano no choque con uno
 * de verdad.
 */
const GRUPO_HUERFANO = "\u0000sin-atributo:";

/**
 * ¿Le toca esta línea a la combinación elegida? Puerto literal de
 * `inventory/domain/rules.aplica_a_variante` (RN-COM-037): se agrupan los
 * valores de la condición **por atributo** y la combinación tiene que
 * coincidir con **al menos uno de cada grupo**. Entre grupos es Y; dentro de
 * un grupo es O.
 *
 * Vive acá y no como copia inline en `fusionar` porque es la misma regla que
 * decide qué se descuenta en el servidor: si el lienzo la calculara distinto,
 * el costo mostrado y el que sale de vender el plato dejarían de coincidir,
 * que es justo el bug que esta función corrige.
 */
export function aplicaAVariante(
  aplicaValores: readonly string[] | null | undefined,
  elegidos: readonly string[],
  atributoDe: Map<string, string>,
): boolean {
  if (!aplicaValores || aplicaValores.length === 0) return true;
  const disponibles = new Set(elegidos);
  if (disponibles.size === 0) return false;
  const grupos = new Map<string, Set<string>>();
  for (const valor of aplicaValores) {
    const clave = atributoDe.get(valor) ?? `${GRUPO_HUERFANO}${valor}`;
    const grupo = grupos.get(clave) ?? new Set<string>();
    grupo.add(valor);
    grupos.set(clave, grupo);
  }
  for (const grupo of grupos.values()) {
    if (![...grupo].some((v) => disponibles.has(v))) return false;
  }
  return true;
}

/** Suma un insumo al acumulado, o lo funde con lo que ya había: el mismo
 * insumo desde dos tramos se suma en una línea (cocina pesa el queso una
 * vez, no dos), y el origen conserva de dónde salió cada aporte. Aparte de
 * `fusionar` solo para no empujar su complejidad ciclomática. */
function acumularLinea(
  porArticulo: Map<string, LineaFusionada>,
  item: RecetaItem,
  tituloDeParte: string,
  cantidad: number,
  costo: number,
  quitado: boolean,
): void {
  const previa = porArticulo.get(item.articulo_id);
  if (!previa) {
    porArticulo.set(item.articulo_id, {
      articuloId: item.articulo_id,
      articulo: item.articulo_nombre,
      unidad: item.unidad_medida_nombre,
      cantidad,
      costo,
      origen: tituloDeParte,
      quitado,
    });
    return;
  }
  previa.cantidad += cantidad;
  previa.costo += costo;
  if (!previa.origen.includes(tituloDeParte)) {
    previa.origen += ` + ${tituloDeParte}`;
  }
}

export function fusionar(
  partes: ParteDeReceta[],
  sinArticuloIds: string[] = [],
  valoresElegidos: readonly string[] = [],
  atributoDe: Map<string, string> = new Map(),
): Fusion {
  const sin = new Set(sinArticuloIds);
  const porArticulo = new Map<string, LineaFusionada>();

  for (const parte of partes) {
    if (!parte.receta) continue;
    const porPlato = rendimiento(parte.receta);
    const veces = parte.veces ?? 1;
    for (const item of parte.receta.items) {
      // La misma regla que descuenta el servidor (RN-COM-037): una línea
      // condicionada a una mitad que no se eligió no se prepara, y sumarla
      // igual es lo que hacía que el costo simulado quedara por encima del
      // real.
      if (!aplicaAVariante(item.aplica_valores, valoresElegidos, atributoDe)) {
        continue;
      }
      acumularLinea(
        porArticulo,
        item,
        parte.titulo,
        (Number(item.cantidad) / porPlato) * veces,
        (Number(item.costo_linea) / porPlato) * veces,
        sin.has(item.articulo_id),
      );
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

/**
 * Las líneas de la receta que nombran este valor en su condición.
 *
 * Pertenencia y no igualdad de conjunto: la línea del jamón puede decir
 * "Mitad 1 ∈ {Americana, Hawaiana}" y sale igual al pedir la Americana. Es
 * la vista que necesita el nodo de un sabor —qué pone *él* en la pizza— y no
 * la que decide si la línea aplica al plato entero, que es cosa del servidor
 * (`aplica_a_variante`, RN-COM-037).
 */
export function lineasCondicionadasA(
  items: RecetaItem[],
  ptavId: string,
): RecetaItem[] {
  return items.filter((i) => i.aplica_valores.includes(ptavId));
}

/** Lo que cuesta un subconjunto de líneas, por plato. Divide por el
 * rendimiento con el mismo criterio que `fusionar`: si acá se dividiera
 * distinto, dos partes de la misma pantalla mostrarían números distintos. */
export function costoDeLineas(items: RecetaItem[], rendimientoCantidad: number): number {
  const porPlato =
    Number.isFinite(rendimientoCantidad) && rendimientoCantidad > 0
      ? rendimientoCantidad
      : 1;
  return items.reduce((t, i) => t + Number(i.costo_linea) / porPlato, 0);
}

/**
 * Los insumos que todavía se pueden agregar **con esta condición**.
 *
 * El mismo insumo puede estar dos veces en la receta si cada línea aplica a
 * otra combinación (ADR-056) —el jamón en la Mitad 1 y en la Mitad 2 son dos
 * líneas—, así que filtrar por artículo a secas hacía imposible el caso que
 * el modelo existe para resolver. Lo que sí se filtra es la repetición
 * exacta: mismo artículo y misma condición es el 409 del servidor, y vale
 * más que la opción desaparezca del `<select>` a que el guardado falle.
 */
export function insumosLibres(
  articulos: Articulo[],
  items: RecetaItem[],
  condicion: readonly string[] = [],
): Articulo[] {
  const firma = firmaDeCondicion(condicion);
  const tomados = new Set(
    items
      .filter((i) => firmaDeCondicion(i.aplica_valores) === firma)
      .map((i) => i.articulo_id),
  );
  return articulos.filter((a) => !tomados.has(a.id));
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
