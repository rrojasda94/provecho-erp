/**
 * La regla que este archivo protege: un error nunca se dibuja como lista
 * vacía, y solo el 403 se traga en silencio. Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

// Extensión explícita: Node resuelve ESM por ruta real, no por convención de
// bundler (el resto del frontend importa sin extensión, vía Next/tsc).
import { ApiError } from "./api.ts";
import { esSinPermiso, fallaDe } from "./carga.ts";
import { ErrorApi } from "./cliente-api.ts";

test("lee el status de las dos clases de error del proyecto", () => {
  assert.equal(fallaDe(new ApiError(500, "boom"), "x").status, 500);
  assert.equal(fallaDe(new ErrorApi(503, "boom"), "x").status, 503);
});

test("el mensaje lo pone el llamador y el del servidor queda como detalle", () => {
  const falla = fallaDe(new ErrorApi(500, "Error 500"), "No se pudo cargar los cobrados");
  assert.equal(falla.mensaje, "No se pudo cargar los cobrados");
  assert.equal(falla.detalle, "Error 500");
});

test("una red caída no trae status: no hubo respuesta que leer", () => {
  const falla = fallaDe(new TypeError("fetch failed"), "No se pudo cargar los cobrados");
  assert.equal(falla.status, null);
  assert.equal(falla.detalle, "fetch failed");
  assert.equal(falla.mensaje, "No se pudo cargar los cobrados");
});

test("lo que se lanza sin ser Error tampoco se pierde", () => {
  assert.deepEqual(fallaDe("boom", "No se pudo cargar"), {
    mensaje: "No se pudo cargar",
    detalle: null,
    status: null,
  });
});

test("solo el 403 es 'no te toca'", () => {
  assert.equal(esSinPermiso(fallaDe(new ApiError(403, "Sin permiso"), "x")), true);
  assert.equal(esSinPermiso(fallaDe(new ApiError(401, "Token vencido"), "x")), false);
  assert.equal(esSinPermiso(fallaDe(new ApiError(500, "boom"), "x")), false);
});

test("una red caída NO es falta de permiso — es el caso que se venía tragando", () => {
  assert.equal(esSinPermiso(fallaDe(new TypeError("fetch failed"), "x")), false);
});

test("sin falla no hay nada que ocultar", () => {
  assert.equal(esSinPermiso(null), false);
});
