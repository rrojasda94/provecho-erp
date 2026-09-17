/**
 * Búsqueda en cliente sobre la carta completa (catálogo chico: unas pocas
 * decenas de productos). Sin dependencia nueva ni `pg_trgm` (ADR-103,
 * decisión 9): normaliza acentos, compara trigramas con el coeficiente de
 * Dice y suma un empate exacto de substring, que cubre "mal escrito"
 * (`peperoni` → `Pepperoni`) sin dejar de encontrar `napolitana` dentro de
 * `Pizza Napolitana` por substring exacto.
 *
 * Sin imports: se prueba con `node --test` sin arrastrar Next (mismo
 * criterio que `frontend/lib/geo.ts`).
 */

export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

function trigramas(texto: string): Set<string> {
  const t = `  ${texto} `;
  const set = new Set<string>();
  for (let i = 0; i < t.length - 2; i++) set.add(t.slice(i, i + 3));
  return set;
}

/** Coeficiente de Dice entre dos conjuntos de trigramas: 2·|A∩B| / (|A|+|B|). */
function dice(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let interseccion = 0;
  for (const t of a) if (b.has(t)) interseccion++;
  return (2 * interseccion) / (a.size + b.size);
}

export type Buscable = {
  id: string;
  /** Términos a comparar: nombre, nombres de variantes, nombres de
   * ingredientes. Cuantos más términos, más formas de encontrarlo. */
  terminos: string[];
};

const UMBRAL = 0.3;

/**
 * Puntúa `candidatos` contra `consulta` y devuelve los ids ordenados por
 * relevancia (mayor primero). Un candidato entra si CUALQUIERA de sus
 * términos matchea por substring exacto (score 1) o supera el umbral de
 * similitud (mal escrito) — el mejor término de cada candidato es el que
 * decide su puntaje, no el promedio.
 */
export function buscar(consulta: string, candidatos: Buscable[]): string[] {
  const q = normalizar(consulta);
  if (!q) return candidatos.map((c) => c.id);
  const qTri = trigramas(q);

  const puntajes: { id: string; score: number }[] = [];
  for (const candidato of candidatos) {
    let mejor = 0;
    for (const termino of candidato.terminos) {
      const t = normalizar(termino);
      if (!t) continue;
      if (t.includes(q) || q.includes(t)) {
        mejor = 1;
        break;
      }
      const score = dice(qTri, trigramas(t));
      if (score > mejor) mejor = score;
    }
    if (mejor >= UMBRAL) puntajes.push({ id: candidato.id, score: mejor });
  }
  return puntajes.sort((a, b) => b.score - a.score).map((p) => p.id);
}
