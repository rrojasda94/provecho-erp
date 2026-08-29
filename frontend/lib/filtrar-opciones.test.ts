import assert from "node:assert/strict";
import { test } from "node:test";

import { filtrarOpciones, normalizar, type Opcion } from "./filtrar-opciones.ts";

const CARTA: Opcion[] = [
  { valor: "1", etiqueta: "Bidón de agua" },
  { valor: "2", etiqueta: "Agua San Luis" },
  { valor: "3", etiqueta: "Gáseosa personal", pista: "SKU-771" },
  { valor: "4", etiqueta: "Pizza americana" },
];

test("sin consulta devuelve la lista intacta, sin copiarla", () => {
  assert.equal(filtrarOpciones(CARTA, ""), CARTA);
  assert.equal(filtrarOpciones(CARTA, "   "), CARTA);
});

test("la búsqueda ignora las tildes en los dos sentidos", () => {
  assert.deepEqual(
    filtrarOpciones(CARTA, "gase").map((o) => o.valor),
    ["3"],
  );
  assert.deepEqual(
    filtrarOpciones([{ valor: "x", etiqueta: "Gaseosa" }], "gáse").map((o) => o.valor),
    ["x"],
  );
});

test("lo que empieza con lo tecleado va antes que lo que solo lo contiene", () => {
  assert.deepEqual(
    filtrarOpciones(CARTA, "agua").map((o) => o.valor),
    ["2", "1"],
  );
});

test("se busca también por la pista, que es el código o el SKU", () => {
  assert.deepEqual(
    filtrarOpciones(CARTA, "771").map((o) => o.valor),
    ["3"],
  );
});

test("cada palabra cuenta por separado, sin importar el orden", () => {
  assert.deepEqual(
    filtrarOpciones(CARTA, "luis san").map((o) => o.valor),
    ["2"],
  );
});

test("lo que no coincide no aparece", () => {
  assert.deepEqual(filtrarOpciones(CARTA, "ceviche"), []);
});

test("normalizar deja minúsculas, sin tildes y sin espacios de sobra", () => {
  assert.equal(normalizar("  Cañada Á  "), "canada a");
});
