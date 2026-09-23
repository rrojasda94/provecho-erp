/**
 * Extras y sabores (Mitad x Mitad) de una línea: reglas puras que espejan las
 * de la API (`src/modules/storefront/domain/opciones.py`, que a su vez repite
 * las de `sales`). Acá sirven para guiar al cliente —qué falta elegir, qué ya no
 * se puede combinar, cuánto cuesta—; quien manda es el servidor, que vuelve a
 * validar y a fijar el precio al confirmar (RN-PRC-003).
 *
 * Sin `"use client"` a propósito: son funciones puras y se prueban con
 * `node --test`.
 */

export type ExtraOpcion = {
  id: string;
  nombre: string;
  precio: string;
  maximo: number | null;
  grupo_id: string | null;
  grupo_nombre: string | null;
  grupo_minimo: number;
  grupo_maximo: number | null;
};

export type ValorOpcion = { id: string; nombre: string; precio_extra: string };
export type AtributoOpcion = {
  id: string;
  nombre: string;
  display: string | null;
  valores: ValorOpcion[];
};

/** Lo que ofrece un producto o una presentación para armar la línea. */
export type Opciones = {
  extras: ExtraOpcion[];
  atributos: AtributoOpcion[];
  exclusiones: [string, string][];
};

export type Seleccion = {
  /** `extraId → cantidad por unidad del producto`. */
  extras: Record<string, number>;
  /** `atributoId → valorId elegido` (uno por atributo). */
  valores: Record<string, string>;
};

/** Regla de la marca (`majambo.md` §3.1.8): a una pizza se le suman como mucho 3
 * extras de pago. El sabor de un grupo obligatorio forma parte de la pizza y no
 * cuenta. */
export const MAXIMO_EXTRAS_DE_PAGO = 3;

export const SELECCION_VACIA: Seleccion = { extras: {}, valores: {} };

export const sinOpciones = (op: Opciones): boolean =>
  op.extras.length === 0 && op.atributos.length === 0;

/** Un extra "de pago" es el que el cliente agrega y paga aparte: el que no
 * pertenece a un grupo obligatorio. */
export const esDePago = (e: ExtraOpcion): boolean => e.grupo_id === null || e.grupo_minimo === 0;

export type Grupo = {
  id: string;
  nombre: string | null;
  minimo: number;
  maximo: number | null;
  extras: ExtraOpcion[];
};

export function gruposDe(op: Opciones): Grupo[] {
  const grupos = new Map<string, Grupo>();
  for (const e of op.extras) {
    if (e.grupo_id === null) continue;
    const g = grupos.get(e.grupo_id) ?? {
      id: e.grupo_id,
      nombre: e.grupo_nombre,
      minimo: e.grupo_minimo,
      maximo: e.grupo_maximo,
      extras: [],
    };
    g.extras.push(e);
    grupos.set(e.grupo_id, g);
  }
  return [...grupos.values()];
}

export const extrasSueltos = (op: Opciones): ExtraOpcion[] =>
  op.extras.filter((e) => e.grupo_id === null);

const elegidos = (sel: Seleccion): [string, number][] =>
  Object.entries(sel.extras).filter(([, cantidad]) => cantidad > 0);

export function extrasDePagoElegidos(op: Opciones, sel: Seleccion): number {
  const porId = new Map(op.extras.map((e) => [e.id, e]));
  return elegidos(sel).reduce((acc, [id, cantidad]) => {
    const extra = porId.get(id);
    return extra && esDePago(extra) ? acc + cantidad : acc;
  }, 0);
}

/** ¿Elegir este valor chocaría con otro ya elegido (mismo sabor en las dos
 * mitades)? Sirve para apagar la opción en pantalla, no para validar. */
export function valorEnConflicto(op: Opciones, sel: Seleccion, valorId: string): boolean {
  const otros = new Set(Object.values(sel.valores));
  otros.delete(valorId);
  return op.exclusiones.some(
    ([a, b]) => (a === valorId && otros.has(b)) || (b === valorId && otros.has(a)),
  );
}

/** Qué le falta o le sobra a la selección, en una frase para el cliente. `null`
 * si se puede agregar. */
export function validar(op: Opciones, sel: Seleccion): string | null {
  for (const a of op.atributos) {
    if (!sel.valores[a.id]) return `Elige ${a.nombre}`;
  }
  const valores = Object.values(sel.valores);
  if (op.exclusiones.some(([a, b]) => valores.includes(a) && valores.includes(b))) {
    return "Esa combinación no se puede pedir: elige opciones distintas";
  }
  for (const g of gruposDe(op)) {
    const cuantos = g.extras.filter((e) => (sel.extras[e.id] ?? 0) > 0).length;
    const etiqueta = g.nombre ?? "una opción";
    if (cuantos < g.minimo) return `Elige ${etiqueta}`;
    if (g.maximo !== null && cuantos > g.maximo) return `${etiqueta} admite hasta ${g.maximo}`;
  }
  for (const e of op.extras) {
    if (e.maximo !== null && (sel.extras[e.id] ?? 0) > e.maximo) {
      return `«${e.nombre}» admite hasta ${e.maximo}`;
    }
  }
  if (extrasDePagoElegidos(op, sel) > MAXIMO_EXTRAS_DE_PAGO) {
    return `Máximo ${MAXIMO_EXTRAS_DE_PAGO} extras por producto`;
  }
  return null;
}

/** Lo que suman los sabores elegidos (recargo de la Hawaiana, etc.). */
export function recargoDeValores(op: Opciones, sel: Seleccion): number {
  const elegidosIds = new Set(Object.values(sel.valores));
  return op.atributos
    .flatMap((a) => a.valores)
    .filter((v) => elegidosIds.has(v.id))
    .reduce((acc, v) => acc + Number(v.precio_extra), 0);
}

/** Lo que suman los extras elegidos, por unidad del producto. */
export function extrasPorUnidad(op: Opciones, sel: Seleccion): number {
  const porId = new Map(op.extras.map((e) => [e.id, e]));
  return elegidos(sel).reduce((acc, [id, cantidad]) => {
    const extra = porId.get(id);
    return extra ? acc + Number(extra.precio) * cantidad : acc;
  }, 0);
}

/** Precio de UNA unidad de la línea: producto + sabores + extras. */
export const precioUnitario = (base: number, op: Opciones, sel: Seleccion): number =>
  base + recargoDeValores(op, sel) + extrasPorUnidad(op, sel);
