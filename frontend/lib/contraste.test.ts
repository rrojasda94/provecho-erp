import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

/**
 * Contraste WCAG de los pares de tokens que el ERP usa como texto sobre
 * superficie, en claro y en oscuro, leídos de `globals.css`.
 *
 * El modo oscuro se entregó con utilidades de marca (`text-dark`,
 * `text-gray`) colgadas de valores que no cambiaban con el tema: texto casi
 * negro sobre fondo casi negro, y nada lo detectaba porque nadie miraba el
 * CSS con los dos temas a la vez. Esto lo mira.
 */

const CSS = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

/** Las declaraciones `--x: valor;` del primer bloque cuyo selector es exacto. */
function bloque(selector: string): Map<string, string> {
  const inicio = CSS.search(new RegExp(`^${selector.replace(/[.[\]]/g, "\\$&")} \\{`, "m"));
  assert.ok(inicio >= 0, `no está el bloque ${selector}`);
  const cuerpo = CSS.slice(inicio, CSS.indexOf("\n}", inicio));
  const mapa = new Map<string, string>();
  for (const m of cuerpo.matchAll(/(--[\w-]+):\s*([^;]+);/g)) mapa.set(m[1], m[2].trim());
  return mapa;
}

const RAIZ = bloque(":root");
const OSCURO = new Map([...RAIZ, ...bloque(".dark")]);
// Las superficies de estado se declaran en un bloque compartido por los dos temas.
const ESTADOS = bloque(":root,\n.dark,\n[data-paleta]");

type Rgb = [number, number, number];

function hex(valor: string): Rgb {
  const h = valor.replace("#", "");
  const largo = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return [0, 2, 4].map((i) => parseInt(largo.slice(i, i + 2), 16)) as Rgb;
}

/** Resuelve `var()`, hex y `color-mix(in srgb, A N%, B)`; `transparent` se
 * compone sobre `fondo`. */
function color(valor: string, tokens: Map<string, string>, fondo: Rgb): Rgb {
  const v = valor.trim();
  if (v.startsWith("#")) return hex(v);
  if (v === "transparent") return fondo;
  const ref = v.match(/^var\((--[\w-]+)\)$/);
  if (ref) {
    const siguiente = tokens.get(ref[1]) ?? ESTADOS.get(ref[1]);
    assert.ok(siguiente, `token sin valor: ${ref[1]}`);
    return color(siguiente, tokens, fondo);
  }
  const mezcla = v.match(/^color-mix\(in srgb,\s*(.+?)\s+(\d+)%,\s*(.+)\)$/);
  assert.ok(mezcla, `no sé leer: ${v}`);
  const a = color(mezcla[1], tokens, fondo);
  const b = color(mezcla[3], tokens, fondo);
  const p = Number(mezcla[2]) / 100;
  return a.map((c, i) => Math.round(c * p + b[i] * (1 - p))) as Rgb;
}

function luminancia([r, g, b]: Rgb): number {
  const canal = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

function contraste(a: Rgb, b: Rgb): number {
  const [claro, oscuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (claro + 0.05) / (oscuro + 0.05);
}

/** [texto, superficie]: lo que el código pinta uno sobre otro. */
const PARES: [string, string][] = [
  ["--foreground", "--background"],
  ["--foreground", "--card"],
  ["--foreground", "--superficie-crema"],
  ["--muted-foreground", "--background"],
  ["--muted-foreground", "--card"],
  ["--muted-foreground", "--muted"],
  ["--primary", "--card"],
  ["--primary", "--background"],
  ["--primary-foreground", "--primary"],
  ["--secondary", "--card"],
  ["--secondary-foreground", "--secondary"],
  ["--status-success", "--status-success-surface"],
  ["--status-danger", "--status-danger-surface"],
  ["--status-warning-texto", "--status-warning-surface"],
  ["--status-info", "--status-info-surface"],
];

for (const [tema, tokens] of [
  ["claro", RAIZ],
  ["oscuro", OSCURO],
] as const) {
  test(`modo ${tema}: todo texto sobre su superficie llega a AA (4.5:1)`, () => {
    const card = color("var(--card)", tokens, [255, 255, 255]);
    const fallas = PARES.map(([texto, fondo]) => {
      const f = color(`var(${fondo})`, tokens, card);
      const ratio = contraste(color(`var(${texto})`, tokens, f), f);
      return { par: `${texto} sobre ${fondo}`, ratio: Math.round(ratio * 100) / 100 };
    }).filter((r) => r.ratio < 4.5);
    assert.deepEqual(fallas, [], `pares bajo 4.5:1 en modo ${tema}`);
  });
}
