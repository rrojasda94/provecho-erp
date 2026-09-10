/**
 * `distanciaMetros` espeja `src/shared/ubicacion.py::metros_entre`: mismo
 * radio de la Tierra, mismo resultado. `decodificarPolyline` se prueba
 * contra el ejemplo canónico que publica Google en su propia documentación
 * del algoritmo. Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { decodificarPolyline, distanciaMetros } from "./geo.ts";

test("un punto contra sí mismo está a 0 metros", () => {
  assert.equal(distanciaMetros({ lat: -12.05, lng: -77.04 }, { lat: -12.05, lng: -77.04 }), 0);
});

test("es simétrica", () => {
  const a = { lat: -12.05, lng: -77.04 };
  const b = { lat: -12.10, lng: -77.02 };
  assert.equal(distanciaMetros(a, b), distanciaMetros(b, a));
});

test("un grado de longitud en el ecuador son ~111.2 km", () => {
  const metros = distanciaMetros({ lat: 0, lng: 0 }, { lat: 0, lng: 1 });
  assert.ok(Math.abs(metros - 111_195) < 10, `esperaba ~111195, dio ${metros}`);
});

test("decodifica el ejemplo canónico de Google", () => {
  const puntos = decodificarPolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@");
  assert.equal(puntos.length, 3);
  assert.ok(Math.abs(puntos[0].lat - 38.5) < 1e-4);
  assert.ok(Math.abs(puntos[0].lng - -120.2) < 1e-4);
  assert.ok(Math.abs(puntos[1].lat - 40.7) < 1e-4);
  assert.ok(Math.abs(puntos[1].lng - -120.95) < 1e-4);
  assert.ok(Math.abs(puntos[2].lat - 43.252) < 1e-4);
  assert.ok(Math.abs(puntos[2].lng - -126.453) < 1e-4);
});

test("una cadena vacía no tiene puntos", () => {
  assert.deepEqual(decodificarPolyline(""), []);
});
