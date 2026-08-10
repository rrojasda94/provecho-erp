/**
 * Checks del mapa de destinos (ADR-036): a qué pantalla lleva cada
 * `referencia_tipo` y cómo se sube al tope la fila que vino del reporte.
 * Corre con `node:test`, igual que `reportes.test.ts`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { etiquetaDestino, primeroElDe, rutaDestino } from "./destinos.ts";

test("la ruta se arma con el id interpolado", () => {
  assert.equal(rutaDestino("venta", "v1"), "/ventas/v1");
  assert.equal(rutaDestino("ajuste", "a1"), "/inventario/ajustes?ajuste=a1");
  assert.equal(rutaDestino("cierre_caja", "c1"), "/contabilidad/caja?cierre=c1");
});

test("sin tipo, sin id o con un tipo desconocido no hay destino", () => {
  // Un reporte sin referencia no es un error: la ficha no dibuja el botón,
  // en vez de mandar a una pantalla que no existe.
  assert.equal(rutaDestino(null, "x"), null);
  assert.equal(rutaDestino("venta", null), null);
  assert.equal(rutaDestino("tipo_que_no_existe", "x"), null);
});

test("el rótulo cae en uno genérico si el tipo no está mapeado", () => {
  assert.equal(etiquetaDestino("venta"), "Ver la venta");
  assert.equal(etiquetaDestino("desconocido"), "Ver el detalle");
  assert.equal(etiquetaDestino(null), "Ver el detalle");
});

const FILAS = [{ id: "a" }, { id: "b" }, { id: "c" }];

test("el que vino del reporte sube al tope y el resto sigue estando", () => {
  const orden = primeroElDe(FILAS, "c", (f) => f.id).map((f) => f.id);
  assert.equal(orden[0], "c");
  assert.deepEqual([...orden].sort(), ["a", "b", "c"]);
});

test("no muta el arreglo original", () => {
  primeroElDe(FILAS, "c", (f) => f.id);
  assert.deepEqual(
    FILAS.map((f) => f.id),
    ["a", "b", "c"],
  );
});

test("sin id la lista vuelve tal cual", () => {
  assert.equal(primeroElDe(FILAS, null, (f) => f.id), FILAS);
});

test("un id ausente no altera el orden", () => {
  assert.deepEqual(
    primeroElDe(FILAS, "zzz", (f) => f.id).map((f) => f.id),
    ["a", "b", "c"],
  );
});
