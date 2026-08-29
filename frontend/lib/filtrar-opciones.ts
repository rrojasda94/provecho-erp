/**
 * El filtrado por texto de los desplegables con búsqueda (`components/ui/combobox`).
 *
 * Vive en `lib/` y no dentro del componente por una razón práctica: las pruebas
 * del frontend son `node --test lib/*.test.ts` sobre lógica pura —no hay
 * testing-library— así que esto es lo único de la búsqueda que el CI puede
 * vigilar. El componente queda como pura presentación.
 *
 * Dos decisiones que se notan al usarlo:
 *
 * - **Se ignoran las tildes en ambos sentidos**: "gase" encuentra "Gáseosa" y
 *   "gáse" encuentra "Gaseosa". Quien busca un producto en una caja con prisa
 *   no acentúa, y un catálogo cargado por importación tiene las dos formas.
 * - **Lo que empieza con lo tecleado va primero**. Buscando "agua", "Agua San
 *   Luis" tiene que salir antes que "Bidón de agua", aunque el catálogo las
 *   ordene al revés.
 */

export type Opcion = {
  valor: string;
  etiqueta: string;
  /** Segunda línea *y* campo buscable: el código del artículo, el SKU, el RUC
   * del proveedor. Se busca acá además de en la etiqueta porque quien tiene el
   * código a mano lo teclea en vez del nombre. */
  pista?: string;
};

/** Minúsculas y sin diacríticos. NFD separa la letra de su tilde y el rango
 * borra las tildes sueltas, así que "Ñ" queda en "n" — que es lo que espera
 * quien escribe "canada" buscando "Cañada". */
export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

/**
 * Las opciones que coinciden con `consulta`, con las que empiezan por ella
 * adelante. Sin consulta devuelve la lista tal cual —misma referencia— para
 * que abrir el desplegable no recalcule nada.
 *
 * Cada palabra de la consulta tiene que aparecer en algún lado ("san luis" y
 * "luis san" encuentran lo mismo): quien busca no recuerda el orden exacto del
 * nombre, y exigir la frase literal convierte un acierto en un "sin
 * resultados".
 */
export function filtrarOpciones<T extends Opcion>(opciones: readonly T[], consulta: string): T[] {
  const buscado = normalizar(consulta);
  if (!buscado) return opciones as T[];

  const palabras = buscado.split(/\s+/);
  const empiezan: T[] = [];
  const contienen: T[] = [];

  for (const opcion of opciones) {
    const etiqueta = normalizar(opcion.etiqueta);
    const heno = opcion.pista ? `${etiqueta} ${normalizar(opcion.pista)}` : etiqueta;
    if (!palabras.every((palabra) => heno.includes(palabra))) continue;
    if (etiqueta.startsWith(palabras[0])) empiezan.push(opcion);
    else contienen.push(opcion);
  }

  return empiezan.concat(contienen);
}
