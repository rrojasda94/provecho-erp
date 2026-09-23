import assert from "node:assert/strict";
import { test } from "node:test";

import { esConfiable, siguienteActivo } from "./direcciones.ts";

/** Un `GeocoderResult` mínimo: solo lo que `esConfiable` mira. */
function resultado(over: {
  partial_match?: boolean;
  location_type?: string;
  types?: string[];
}): google.maps.GeocoderResult {
  return {
    partial_match: over.partial_match ?? false,
    geometry: { location_type: over.location_type ?? "ROOFTOP" },
    types: over.types ?? ["street_address"],
  } as unknown as google.maps.GeocoderResult;
}

test("un geocode ROOFTOP limpio se puede anclar solo", () => {
  assert.equal(esConfiable(resultado({})), true);
});

test("una interpolación de cuadra también alcanza (caso Tarapoto)", () => {
  assert.equal(esConfiable(resultado({ location_type: "RANGE_INTERPOLATED" })), true);
});

test("un match parcial no se ancla aunque la precisión sea ROOFTOP", () => {
  assert.equal(esConfiable(resultado({ partial_match: true })), false);
});

test("el centro geométrico de una calle no se ancla: puede quedar lejísimos", () => {
  assert.equal(esConfiable(resultado({ location_type: "GEOMETRIC_CENTER" })), false);
});

test("el centroide aproximado de una zona no se ancla", () => {
  assert.equal(
    esConfiable(resultado({ location_type: "APPROXIMATE", types: ["locality"] })),
    false,
  );
});

test("un tipo vago no se ancla aunque la precisión pase", () => {
  assert.equal(
    esConfiable(resultado({ location_type: "ROOFTOP", types: ["locality"] })),
    false,
  );
});

test("siguienteActivo baja una fila con ArrowDown", () => {
  assert.equal(siguienteActivo(0, 5, "ArrowDown"), 1);
});

test("siguienteActivo envuelve de la última fila a la primera", () => {
  assert.equal(siguienteActivo(4, 5, "ArrowDown"), 0);
});

test("siguienteActivo sube una fila con ArrowUp", () => {
  assert.equal(siguienteActivo(2, 5, "ArrowUp"), 1);
});

test("siguienteActivo envuelve de ninguna fila activa hacia arriba, a la última", () => {
  assert.equal(siguienteActivo(-1, 5, "ArrowUp"), 4);
});

test("siguienteActivo con la lista vacía siempre devuelve -1", () => {
  assert.equal(siguienteActivo(0, 0, "ArrowDown"), -1);
  assert.equal(siguienteActivo(-1, 0, "ArrowUp"), -1);
});

test("una tecla que no es flecha no mueve el resaltado", () => {
  assert.equal(siguienteActivo(2, 5, "Tab"), 2);
});
