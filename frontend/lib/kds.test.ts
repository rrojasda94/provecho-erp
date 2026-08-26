/**
 * Único check de la lógica no trivial del KDS: qué pasos manda un toque
 * sobre un ítem. Corre con `npm run test:kds` — `node:test` y el soporte de
 * TypeScript ya vienen en Node 22+, no hay framework que instalar.
 */

import assert from "node:assert/strict";
import test from "node:test";

// Extensión explícita: Node resuelve ESM por ruta real, no por convención de
// bundler (el resto del frontend importa sin extensión, vía Next/tsc).
import { pasosHastaListo, siguienteToque } from "./kds-avance.ts";

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

test("hacen falta dos toques para que la línea salga de la estación", () => {
  // Antes un toque encadenaba los dos pasos y el roce de un delantal
  // despachaba el plato. El primero dice "lo estoy haciendo".
  assert.equal(siguienteToque("pendiente"), "en_preparacion");
  // El segundo es el que la manda a la pantalla siguiente.
  assert.equal(siguienteToque("en_preparacion"), "listo");
});

test("un toque nunca entrega: eso es un acto de despacho (RN-CUP-006)", () => {
  assert.equal(siguienteToque("listo"), null);
  assert.equal(siguienteToque("entregado"), null);
});
