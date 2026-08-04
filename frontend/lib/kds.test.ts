/**
 * Único check de la lógica no trivial del KDS: qué pasos manda un toque
 * sobre un ítem. Corre con `npm run test:kds` — `node:test` y el soporte de
 * TypeScript ya vienen en Node 22+, no hay framework que instalar.
 */

import assert from "node:assert/strict";
import test from "node:test";

// Extensión explícita: Node resuelve ESM por ruta real, no por convención de
// bundler (el resto del frontend importa sin extensión, vía Next/tsc).
import { pasosHastaListo } from "./kds-avance.ts";

test("desde pendiente pasa por en_preparacion antes de listo", () => {
  assert.deepEqual(pasosHastaListo("pendiente"), ["en_preparacion", "listo"]);
});

test("desde en_preparacion solo falta listo", () => {
  assert.deepEqual(pasosHastaListo("en_preparacion"), ["listo"]);
});

test("un ítem ya listo no vuelve a avanzar (RN-CUP-002: sin retroceso)", () => {
  assert.deepEqual(pasosHastaListo("listo"), []);
  assert.deepEqual(pasosHastaListo("entregado"), []);
});
