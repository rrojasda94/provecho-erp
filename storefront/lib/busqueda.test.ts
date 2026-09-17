import assert from "node:assert/strict";
import test from "node:test";

import { buscar, normalizar } from "./busqueda.ts";

const CARTA = [
  { id: "peperoni", terminos: ["Pizza Peperoni", "Personal", "Mediana", "Familiar"] },
  { id: "hawaiana", terminos: ["Pizza Hawaiana", "Jamón", "Piña", "Queso mozzarella"] },
  { id: "caprichosa", terminos: ["Caprichosa", "Jamón", "Tocino", "Champiñones"] },
  { id: "vegetariana", terminos: ["La Vegetariana", "Champiñones", "Aceitunas"] },
  { id: "napolitana", terminos: ["Napolitana", "Tomate", "Queso mozzarella"] },
];

test("normalizar quita tildes y pasa a minúsculas", () => {
  assert.equal(normalizar("Peperoní"), "peperoni");
  assert.equal(normalizar("  Champiñón  "), "champinon");
});

test("substring exacto encuentra por nombre", () => {
  assert.deepEqual(buscar("napolitana", CARTA), ["napolitana"]);
});

test("nombre mal escrito encuentra por similitud", () => {
  const resultados = buscar("hawayana", CARTA);
  assert.ok(resultados.includes("hawaiana"), `esperaba encontrar hawaiana, dio ${resultados}`);
});

test("otro nombre mal escrito, con una letra de más", () => {
  const resultados = buscar("peperonni", CARTA);
  assert.ok(resultados.includes("peperoni"), `esperaba encontrar peperoni, dio ${resultados}`);
});

test("busca por ingrediente y encuentra todas las que lo llevan", () => {
  const resultados = buscar("champiñon", CARTA);
  assert.ok(resultados.includes("caprichosa"));
  assert.ok(resultados.includes("vegetariana"));
  assert.ok(!resultados.includes("napolitana"));
});

test("consulta vacía devuelve todo en el orden original", () => {
  assert.deepEqual(
    buscar("", CARTA),
    CARTA.map((c) => c.id),
  );
});

test("consulta sin ninguna coincidencia devuelve vacío", () => {
  assert.deepEqual(buscar("zzzzz-no-existe", CARTA), []);
});
