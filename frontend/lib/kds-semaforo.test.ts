/**
 * El semáforo es lo único del KDS que puede fallar sin que nadie se entere:
 * un pedido que nunca se pone rojo no avisa de nada, y eso no se nota
 * mirando la pantalla. Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { minutosDesde, nivelDe, reloj, type Semaforo } from "./kds-semaforo.ts";

const S: Semaforo = {
  minutos_ambar: 8,
  minutos_rojo: 15,
  color_normal: "#22c55e",
  color_ambar: "#fbbf24",
  color_rojo: "#f87171",
};

test("el nivel cambia justo al cumplirse el umbral, no después", () => {
  assert.equal(nivelDe(0, S), "normal");
  assert.equal(nivelDe(7, S), "normal");
  assert.equal(nivelDe(8, S), "ambar");
  assert.equal(nivelDe(14, S), "ambar");
  assert.equal(nivelDe(15, S), "rojo");
});

test("con los umbrales pegados el rojo sigue siendo alcanzable", () => {
  // Preguntar por el ámbar primero dejaba el rojo inalcanzable con
  // `ambar: 8, rojo: 9`.
  const pegados = { ...S, minutos_ambar: 8, minutos_rojo: 9 };
  assert.equal(nivelDe(9, pegados), "rojo");
  assert.equal(nivelDe(8, pegados), "ambar");
});

test("los minutos se cuentan desde que se tomó el pedido", () => {
  const ahora = Date.parse("2026-08-26T12:30:00Z");
  assert.equal(minutosDesde("2026-08-26T12:18:00Z", ahora), 12);
  // Reloj corrido o pedido del futuro: nunca negativo.
  assert.equal(minutosDesde("2026-08-26T12:45:00Z", ahora), 0);
});

test("una fecha ilegible se pinta como recién llegada, no como roja", () => {
  assert.equal(minutosDesde("no es una fecha"), 0);
});

test("pasada la hora el reloj deja de leerse en minutos", () => {
  assert.equal(reloj(12), "12 min");
  assert.equal(reloj(59), "59 min");
  assert.equal(reloj(75), "1 h 15 min");
});
