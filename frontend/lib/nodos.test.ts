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

import type { Articulo, RecetaItem } from "./catalogo.ts";
import {
  aplicaAVariante,
  cantidadCorta,
  costoDeLineas,
  fusionar,
  insumosLibres,
  lineasCondicionadasA,
  margen,
} from "./nodos.ts";

function receta(
  rendimiento: string,
  items: [string, string, string][],
  condiciones: string[][] = [],
) {
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
      aplica_valores: condiciones[i] ?? [],
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


// --- La condición de una línea (RN-COM-037, ADR-056) -----------------------
// La mitad-y-mitad: el jamón entra dos veces en la misma receta, una por
// mitad, y cada línea nombra los sabores que la disparan.
const MITADES = receta(
  "1",
  [
    ["masa", "1", "3.00"],
    ["jamon", "12.5", "1.00"],
    ["jamon", "12.5", "1.00"],
  ],
  [[], ["m1_ame", "m1_haw"], ["m2_ame", "m2_haw"]],
);

test("las líneas de un sabor son las que lo nombran, no las que lo igualan", () => {
  // La condición dice "Mitad 1 ∈ {Americana, Hawaiana}": pedir la Americana
  // tiene que traerla igual, aunque el conjunto no sea exactamente ese.
  const suyas = lineasCondicionadasA(MITADES.items as RecetaItem[], "m1_ame");
  assert.equal(suyas.length, 1);
  assert.deepEqual(suyas[0].aplica_valores, ["m1_ame", "m1_haw"]);

  // La línea sin condición NO es de ningún sabor en particular: es del plato.
  assert.equal(
    lineasCondicionadasA(MITADES.items as RecetaItem[], "m2_ame").length,
    1,
  );
  assert.equal(
    lineasCondicionadasA(MITADES.items as RecetaItem[], "m1_pep").length,
    0,
  );
});

test("el costo de un subconjunto de líneas divide por el rendimiento", () => {
  const dos = MITADES.items.slice(1) as RecetaItem[];
  assert.equal(costoDeLineas(dos, 1), 2);
  assert.equal(costoDeLineas(dos, 4), 0.5);
  // Un rendimiento imposible no puede dividir por cero ni por negativo.
  assert.equal(costoDeLineas(dos, 0), 2);
});

test("el mismo insumo sigue disponible bajo otra condición", () => {
  const articulos = [
    { id: "masa", nombre: "Masa" },
    { id: "jamon", nombre: "Jamón" },
  ] as Articulo[];
  const items = MITADES.items as RecetaItem[];

  // Con la condición de la Mitad 1 el jamón ya está: repetirlo sería el 409
  // del servidor. Con la de la Mitad 2 también. Con otra, entra.
  assert.deepEqual(
    insumosLibres(articulos, items, ["m1_ame", "m1_haw"]).map((a) => a.id),
    ["masa"],
  );
  assert.deepEqual(
    insumosLibres(articulos, items, ["m1_pep"]).map((a) => a.id),
    ["masa", "jamon"],
  );
  // Sin condición solo está tomada la masa, que es la línea que aplica
  // siempre.
  assert.deepEqual(
    insumosLibres(articulos, items, []).map((a) => a.id),
    ["jamon"],
  );
});

test("el orden de los valores no hace a la condición", () => {
  const articulos = [{ id: "jamon", nombre: "Jamón" }] as Articulo[];
  assert.deepEqual(
    insumosLibres(articulos, MITADES.items as RecetaItem[], ["m1_haw", "m1_ame"]),
    [],
  );
});


// --- `fusionar` respeta la condición (RN-COM-037) ---------------------------
// El atributo_de: dos mitades, tres sabores cada una.
const ATRIBUTO_DE = new Map([
  ["m1_ame", "mitad1"], ["m1_haw", "mitad1"], ["m1_pep", "mitad1"],
  ["m2_ame", "mitad2"], ["m2_haw", "mitad2"], ["m2_pep", "mitad2"],
]);

test("aplicaAVariante: sin condición aplica siempre", () => {
  assert.equal(aplicaAVariante([], [], ATRIBUTO_DE), true);
  assert.equal(aplicaAVariante(null, ["m1_ame"], ATRIBUTO_DE), true);
});

test("aplicaAVariante: con condición y sin elección no aplica", () => {
  // Vender sin elegir nada no puede disparar una línea condicionada.
  assert.equal(aplicaAVariante(["m1_ame"], [], ATRIBUTO_DE), false);
});

test("aplicaAVariante: entre grupos es Y, dentro del grupo es O", () => {
  const condicion = ["m1_ame", "m1_haw", "m2_ame", "m2_haw"];
  // Las dos mitades calificaron: aplica.
  assert.equal(aplicaAVariante(condicion, ["m1_ame", "m2_haw"], ATRIBUTO_DE), true);
  // Solo una mitad calificó: no aplica — media americana + media peperoni
  // no descuenta el jamón (ADR-056 §2).
  assert.equal(aplicaAVariante(condicion, ["m1_ame", "m2_pep"], ATRIBUTO_DE), false);
});

test("aplicaAVariante: un valor huérfano forma su propio grupo", () => {
  // Lectura conservadora: mejor no aplicar que descontar de más.
  assert.equal(aplicaAVariante(["fantasma"], ["m1_ame"], ATRIBUTO_DE), false);
  assert.equal(aplicaAVariante(["fantasma"], ["fantasma"], ATRIBUTO_DE), true);
});

test("fusionar sin elección no suma las líneas condicionadas", () => {
  const conCondicion = {
    titulo: "Familiar",
    tipo: "tamano" as const,
    receta: receta("1", [
      ["masa", "1", "3.00"],
      ["jamon", "12.5", "1.00"],
    ], [[], ["m1_ame", "m1_haw"]]),
  };
  // Sin elegir sabor, la línea condicionada no se prepara: solo la masa
  // aparece en el plato.
  const { lineas } = fusionar([conCondicion], [], [], ATRIBUTO_DE);
  assert.deepEqual(lineas.map((l) => l.articuloId), ["masa"]);
});

test("fusionar con la mitad elegida suma solo lo que le toca", () => {
  const mitades = {
    titulo: "Familiar",
    tipo: "tamano" as const,
    receta: receta("1", [
      ["masa", "1", "3.00"],
      ["jamon", "12.5", "1.00"],
      ["jamon", "12.5", "1.00"],
    ], [[], ["m1_ame", "m1_haw"], ["m2_pep"]]),
  };
  // Mitad 1 Americana, Mitad 2 Peperoni: el jamón de la Mitad 1 entra, el
  // que dependía de la Mitad 2 (Peperoni no es su sabor) no.
  const { lineas, costo } = fusionar([mitades], [], ["m1_ame", "m2_ame"], ATRIBUTO_DE);
  const jamon = lineas.find((l) => l.articuloId === "jamon");
  assert.ok(jamon);
  assert.equal(jamon.costo, 1);
  assert.equal(costo, 4); // 3 (masa) + 1 (jamón de una sola mitad)
});

test("fusionar sin atributoDe (llamado viejo) sigue sumando todo", () => {
  // Retrocompatibilidad: los tramos sin condición (todo lo de hoy) no
  // dependen de que el llamador pase el índice de atributos.
  const sinCondicion = {
    titulo: "Base",
    tipo: "tamano" as const,
    receta: receta("1", [["masa", "1", "3.00"]]),
  };
  const { costo } = fusionar([sinCondicion]);
  assert.equal(costo, 3);
});
