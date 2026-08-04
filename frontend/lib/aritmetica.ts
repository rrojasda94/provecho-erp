/**
 * Aritmética tecleada en un campo de cantidad ("1000/3", "250*1.5").
 *
 * Espejo de `src/shared/aritmetica.py`, solo para la vista previa mientras
 * se escribe: **el número que se guarda lo calcula el servidor** a partir
 * de la expresión. Si el navegador mandara el resultado, nada garantizaría
 * que corresponda a la operación que se ve en pantalla.
 *
 * Parser propio de ~40 líneas en vez de `eval` o una dependencia: `eval`
 * ejecuta lo que sea que el usuario pegue, y ninguna librería de
 * expresiones justifica su peso para cuatro operadores.
 */

const OPERADORES = /^[\d\s.+\-*/()]+$/;

/** Resultado de la expresión, o `null` si no es evaluable todavía (el
 * usuario está a medio escribir: "250*" no es un error, es un borrador). */
export function evaluar(expresion: string): number | null {
  const texto = expresion.trim();
  if (!texto || texto.length > 60 || !OPERADORES.test(texto)) return null;
  try {
    const [valor, resto] = suma(texto, 0);
    if (resto < texto.length) return null;
    return Number.isFinite(valor) ? valor : null;
  } catch {
    return null;
  }
}

/** Redondea a los decimales que admite la unidad de medida (RN-GER-010). */
export function redondear(valor: number, decimales: number): number {
  const factor = 10 ** decimales;
  return Math.round(valor * factor) / factor;
}

/** Lo que se muestra en el campo: resultado ya redondeado, con sus
 * decimales fijos ("333.333" y no "333.33299999999997"). */
export function formatear(valor: number, decimales: number): string {
  return redondear(valor, decimales).toFixed(decimales);
}

// --- Descenso recursivo: suma → producto → factor ---------------------------
function suma(t: string, i: number): [number, number] {
  let [valor, pos] = producto(t, i);
  for (;;) {
    pos = saltar(t, pos);
    const op = t[pos];
    if (op !== "+" && op !== "-") return [valor, pos];
    const [derecha, siguiente] = producto(t, pos + 1);
    valor = op === "+" ? valor + derecha : valor - derecha;
    pos = siguiente;
  }
}

function producto(t: string, i: number): [number, number] {
  let [valor, pos] = factor(t, i);
  for (;;) {
    pos = saltar(t, pos);
    const op = t[pos];
    if (op !== "*" && op !== "/") return [valor, pos];
    const [derecha, siguiente] = factor(t, pos + 1);
    if (op === "/" && derecha === 0) throw new Error("división entre cero");
    valor = op === "*" ? valor * derecha : valor / derecha;
    pos = siguiente;
  }
}

function factor(t: string, i: number): [number, number] {
  let pos = saltar(t, i);
  if (t[pos] === "-" || t[pos] === "+") {
    const signo = t[pos] === "-" ? -1 : 1;
    const [valor, siguiente] = factor(t, pos + 1);
    return [signo * valor, siguiente];
  }
  if (t[pos] === "(") {
    const [valor, siguiente] = suma(t, pos + 1);
    if (t[saltar(t, siguiente)] !== ")") throw new Error("paréntesis sin cerrar");
    return [valor, saltar(t, siguiente) + 1];
  }
  const inicio = pos;
  while (pos < t.length && /[\d.]/.test(t[pos])) pos++;
  if (pos === inicio) throw new Error("se esperaba un número");
  const numero = Number(t.slice(inicio, pos));
  if (Number.isNaN(numero)) throw new Error("número inválido");
  return [numero, pos];
}

function saltar(t: string, i: number): number {
  let pos = i;
  while (pos < t.length && t[pos] === " ") pos++;
  return pos;
}
