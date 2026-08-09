/**
 * Check de la fusión de recetas por nodos. Lo no trivial es lo que se
 * prueba acá: que un insumo repetido entre tramos se sume en una línea, que
 * una resta salga del costo, y que el rendimiento divida (una receta que
 * rinde 4 porciones aporta un cuarto por plato).
 *
 * Corre con `npm test` — `node:test` y el soporte de TypeScript ya vienen
 * en Node 22+.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { cantidadCorta, fusionar, margen } from "./nodos.ts";

function receta(rendimiento: string, items: [string, string, string][]) {
  return {
    id: "r",
    nombre: "r",
    rendimiento_cantidad: rendimiento,
    rendimiento_unidad_medida_id: "u",
    rendimiento_unidad_medida_nombre: "Unidad",
    articulo_id: null,
    flexible: false,
    criterio_ajuste: null,
    costo_total: "0",
    items: items.map(([articuloId, cantidad, costo], i) => ({
      id: `i${i}`,
      articulo_id: articuloId,
      articulo_nombre: articuloId,
      unidad_medida_id: "u",
      unidad_medida_nombre: "g",
      decimales: 2,
      cantidad,
      expresion: null,
      merma_pct: "0",
      costo_unitario: "1",
      costo_linea: costo,
    })),
  };
}

const BASE = {
  titulo: "Familiar",
  tipo: "tamano" as const,
  receta: receta("1", [
    ["masa", "1", "3.00"],
    ["queso", "200", "5.00"],
  ]),
};

test("el mismo insumo en dos tramos se suma en una sola línea", () => {
  const { lineas, costo } = fusionar([
    BASE,
    {
      titulo: "Extra queso",
      tipo: "extra",
      receta: receta("1", [["queso", "50", "1.25"]]),
    },
  ]);
  const queso = lineas.find((l) => l.articuloId === "queso");
  assert.equal(queso?.cantidad, 250);
  assert.equal(queso?.origen, "Familiar + Extra queso");
  assert.equal(lineas.length, 2, "no duplica la línea de queso");
  assert.equal(costo, 9.25);
});

test("un extra pedido dos veces aporta el doble", () => {
  const { costo } = fusionar([
    {
      titulo: "Extra queso",
      tipo: "extra",
      receta: receta("1", [["queso", "50", "1.25"]]),
      veces: 2,
    },
  ]);
  assert.equal(costo, 2.5);
});

test("una resta sale del costo pero sigue visible como quitada", () => {
  const { lineas, costo, costoQuitado } = fusionar([BASE], ["queso"]);
  assert.equal(costo, 3);
  assert.equal(costoQuitado, 5);
  assert.equal(lineas.find((l) => l.articuloId === "queso")?.quitado, true);
  assert.equal(
    lineas.length,
    2,
    "el insumo quitado sigue en la lista: cocina tiene que leer 'sin queso'",
  );
});

test("una receta que rinde 4 aporta un cuarto por plato", () => {
  const { costo, lineas } = fusionar([
    {
      titulo: "Salsa",
      tipo: "sabor",
      receta: receta("4", [["tomate", "1000", "8.00"]]),
    },
  ]);
  assert.equal(costo, 2);
  assert.equal(lineas[0].cantidad, 250);
});

test("rendimiento inválido no divide por cero ni por negativo", () => {
  for (const malo of ["0", "-2", "", "x"]) {
    const { costo } = fusionar([
      { titulo: "t", tipo: "sabor", receta: receta(malo, [["a", "1", "4.00"]]) },
    ]);
    assert.equal(costo, 4, `rendimiento "${malo}" debe tratarse como 1`);
  }
});

test("un tramo sin receta elegida no aporta ni rompe", () => {
  const { lineas, costo } = fusionar([
    { titulo: "Sabor", tipo: "sabor", receta: null },
    BASE,
  ]);
  assert.equal(lineas.length, 2);
  assert.equal(costo, 8);
});

test("sin precio el margen no reporta 0 % (que se leería como 'no deja nada')", () => {
  assert.equal(margen(0, 8).pct, null);
  assert.equal(margen(20, 8).pct, 60);
  assert.equal(margen(20, 8).monto, 12);
});

test("las cantidades se muestran sin ceros de relleno", () => {
  assert.equal(cantidadCorta(180), "180");
  assert.equal(cantidadCorta(0.5), "0.5");
  assert.equal(cantidadCorta(1 / 3), "0.3333");
});
