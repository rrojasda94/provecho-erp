/**
 * Lo que hay que elegir para armar una línea del PDV, sin React.
 *
 * Vive en `lib/` y no dentro de `dialogos.tsx` para que `npm test`
 * (`node --test lib/*.test.ts`) lo pueda ejercitar: son las reglas que
 * deciden si una línea se puede guardar, y probarlas a través de la pantalla
 * cuesta un navegador entero.
 *
 * Conviven dos mecanismos y **no son lo mismo**:
 *
 * - **Grupos de extras** (ADR-023/038): cada extra es un `producto_comercial`
 *   que nace como línea propia, se cobra aparte y sale impreso en el ticket.
 *   Se eligen por cantidad.
 * - **Atributos** (ADR-055/056/063): un valor no crea línea — cambia *qué* se
 *   prepara, activando las líneas condicionadas de la receta. Viaja al
 *   servidor por `valores_variante_ids`, no como un extra más, y se elige
 *   exactamente uno por atributo (RN-COM-040).
 *
 * Unificarlos en un solo tipo "opción" sería la abstracción que esconde esa
 * diferencia justo donde importa: al mandar la venta.
 */

import type {
  AtributoDeCarta,
  ExtraDeCarta,
  ItemDeCarta,
  VarianteDeCarta,
} from "./pdv";

export type GrupoDeExtras = {
  id: string | null;
  nombre: string | null;
  minimo: number;
  maximo: number | null;
  extras: ExtraDeCarta[];
};

/** Lo que ofrece la línea: extras agrupados, atributos y sus exclusiones.
 *
 * Todo cuelga del producto que **se prepara**, y con presentaciones ese es la
 * variante: el servidor solo acepta lo vinculado a ELLA, así que mezclar lo
 * del padre armaría líneas que fallan recién al enviar el pedido. Mientras no
 * se elija presentación no se ofrece nada, porque todavía no se sabe qué se
 * prepara. */
export function opcionesOfrecidas(
  item: ItemDeCarta | null,
  variante: VarianteDeCarta | undefined,
): {
  extras: ExtraDeCarta[];
  atributos: AtributoDeCarta[];
  exclusiones: [string, string][];
} {
  const vacio = { extras: [], atributos: [], exclusiones: [] as [string, string][] };
  if (!item) return vacio;
  const nodo = item.variantes.length === 0 ? item : variante;
  if (!nodo) return vacio;
  return {
    extras: nodo.extras,
    atributos: nodo.atributos ?? [],
    exclusiones: nodo.exclusiones ?? [],
  };
}

/** Los extras vienen planos del backend con su grupo adentro; acá se
 * agrupan para dibujarlos. Los sueltos (sin grupo) caen al final, siempre
 * opcionales. */
export function agruparExtras(extras: ExtraDeCarta[]): GrupoDeExtras[] {
  const grupos: GrupoDeExtras[] = [];
  for (const extra of extras) {
    const existente = grupos.find((g) => g.id === extra.grupo_id);
    if (existente) {
      existente.extras.push(extra);
      continue;
    }
    grupos.push({
      id: extra.grupo_id,
      nombre: extra.grupo_nombre,
      minimo: extra.grupo_minimo,
      maximo: extra.grupo_maximo,
      extras: [extra],
    });
  }
  return grupos.sort((a, b) => Number(a.id === null) - Number(b.id === null));
}

export function elegidosEn(
  grupo: GrupoDeExtras,
  extras: Record<string, number>,
): number {
  return grupo.extras.filter((e) => (extras[e.producto_comercial_id] ?? 0) > 0).length;
}

/**
 * Qué valores quedan prohibidos por lo que ya se eligió.
 *
 * La exclusión se guarda una sola fila y vale en los dos sentidos —son el
 * mismo hecho—, así que hay que mirar las dos puntas: comparar en una sola
 * dirección dejaría habilitada la mitad de las pastillas que no van.
 *
 * Un valor no se excluye a sí mismo: en una mitad-y-mitad el par prohibido es
 * «Hawaiana con Hawaiana», y si el ya elegido apagara su propia pastilla, el
 * cajero no podría ver cuál eligió ni cambiarla.
 */
export function ptavExcluidos(
  exclusiones: [string, string][],
  elegidos: Record<string, string>,
): Set<string> {
  const puestos = new Set(Object.values(elegidos).filter(Boolean));
  const apagados = new Set<string>();
  for (const [a, b] of exclusiones) {
    if (puestos.has(a) && !puestos.has(b)) apagados.add(b);
    if (puestos.has(b) && !puestos.has(a)) apagados.add(a);
  }
  return apagados;
}

/** Cuánto suman al precio de la línea los valores elegidos (RN-COM-036).
 *
 * El servidor vuelve a calcularlo al confirmar —es él quien fija el precio
 * (RN-PRC-003)—; acá se suma solo para que el ticket muestre el mismo número
 * que se va a cobrar. */
export function recargoDe(
  atributos: AtributoDeCarta[],
  elegidos: Record<string, string>,
): number {
  let total = 0;
  for (const atributo of atributos) {
    const puesto = elegidos[atributo.atributo_id];
    const valor = atributo.valores.find((v) => v.id === puesto);
    if (valor) total += Number(valor.precio_extra);
  }
  return total;
}

/** Qué le falta a la línea para poder guardarse.
 *
 * Mismo criterio que valida el servidor al confirmar la venta, dicho en el
 * momento en que se puede corregir. Los atributos se recorren aparte de los
 * grupos porque no es la misma regla: un grupo cuenta opciones contra su
 * `minimo`/`maximo`, un atributo es siempre exactamente uno (RN-COM-040). */
export function queFalta(
  variantes: VarianteDeCarta[],
  variante: VarianteDeCarta | undefined,
  grupos: GrupoDeExtras[],
  extras: Record<string, number>,
  atributos: AtributoDeCarta[] = [],
  valores: Record<string, string> = {},
): string | null {
  if (variantes.length > 0 && !variante) return "Elige una presentación";
  for (const atributo of atributos) {
    if (!valores[atributo.atributo_id]) return `Elige ${atributo.nombre}`;
  }
  for (const grupo of grupos) {
    if (elegidosEn(grupo, extras) < grupo.minimo) {
      return `Elige ${grupo.minimo} en ${grupo.nombre ?? "Extras"}`;
    }
  }
  return null;
}
