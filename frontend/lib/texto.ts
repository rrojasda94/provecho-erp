/**
 * Formato título en español, espejo de `src/shared/texto.py`.
 *
 * Se aplica al salir del campo (`onBlur`) para que el usuario vea el nombre
 * ya normalizado antes de guardar. El backend vuelve a aplicarlo: esta capa
 * es comodidad, no la garantía — la API tiene más clientes que esta
 * pantalla. Si las dos implementaciones se separan, el nombre cambia solo
 * al guardar y se nota; por eso la lista de conectores es la misma.
 */

const CONECTORES = new Set([
  "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "e",
  "el", "en", "entre", "hacia", "hasta", "la", "las", "los", "o", "para",
  "por", "según", "sin", "sobre", "tras", "u", "y",
]);

/** "pizza de peperoni familiar" → "Pizza de Peperoni Familiar". */
export function aTitulo(texto: string): string {
  const palabras = texto.split(/\s+/).filter(Boolean);
  return palabras.map((p, i) => palabra(p, i === 0)).join(" ");
}

function palabra(bruta: string, primera: boolean): string {
  // Los compuestos también abren palabra: "coca-cola" → "Coca-Cola".
  return bruta
    .split(/([-/])/)
    .map((parte, i) =>
      parte === "-" || parte === "/" ? parte : trozo(parte, primera && i === 0),
    )
    .join("");
}

function trozo(parte: string, primera: boolean): string {
  if (!parte) return parte;
  // Sigla escrita en mayúscula a propósito (XL, IGV, CH1).
  if (parte.length <= 4 && parte === parte.toUpperCase() && /[A-ZÁÉÍÓÚÑ]/.test(parte)) {
    return parte;
  }
  if (!primera && CONECTORES.has(parte.toLowerCase())) return parte.toLowerCase();
  return parte[0].toUpperCase() + parte.slice(1).toLowerCase();
}
