import assert from "node:assert/strict";
import { test } from "node:test";

import { evaluar } from "./aritmetica.ts";
import {
  armar,
  cambios,
  clave,
  copiar,
  costo,
  escribir,
  haySinGuardar,
  leerPegado,
  pegar,
  recortar,
  type Grilla,
} from "./matriz.ts";

const GRILLA: Grilla = {
  recetas: [
    {
      id: "r1",
      nombre: "Pizza Personal",
      rendimiento_cantidad: "1",
      rendimiento_unidad_medida_id: "u1",
      es_kit: false,
    },
    {
      id: "r2",
      nombre: "Pizza Familiar",
      rendimiento_cantidad: "1",
      rendimiento_unidad_medida_id: "u1",
      es_kit: false,
    },
  ],
  insumos: [
    {
      articulo_id: "a1",
      nombre: "Queso",
      unidad_medida_id: "kg",
      unidad: "kg",
      decimales: 4,
      costo_promedio: "20",
    },
    {
      articulo_id: "a2",
      nombre: "Jamón",
      unidad_medida_id: "kg",
      unidad: "kg",
      decimales: 4,
      costo_promedio: "30",
    },
  ],
  celdas: [
    {
      item_id: "i1",
      receta_id: "r1",
      articulo_id: "a1",
      cantidad: "0.1500",
      expresion: null,
      merma_pct: "0",
      unidad_medida_id: null,
      unidad: "kg",
      decimales: 4,
      aplica_valores: [],
      orden: 0,
    },
    {
      item_id: "i2",
      receta_id: "r2",
      articulo_id: "a1",
      cantidad: "150",
      expresion: "450/3",
      merma_pct: "0",
      unidad_medida_id: null,
      unidad: "kg",
      decimales: 4,
      aplica_valores: [],
      orden: 1,
    },
  ],
};

test("la clave no depende del orden de la condición", () => {
  assert.equal(clave("r", "a", ["x", "y"]), clave("r", "a", ["y", "x"]));
  assert.notEqual(clave("r", "a", ["x"]), clave("r", "a", ["x", "y"]));
});

test("se muestra lo tecleado, no el resultado", () => {
  // Quien escribió "450/3" quiere volver a ver la división (RN-COM-024).
  const modelo = armar(GRILLA);
  assert.equal(modelo.celdas.get(clave("r2", "a1"))?.texto, "450/3");
});

test("los ceros de la derecha de Numeric no se muestran", () => {
  assert.equal(recortar("0.1500", 4), "0.15");
  assert.equal(recortar("150", 4), "150");
  assert.equal(recortar("0", 4), "");
});

test("una celda vacía en el servidor no entra al modelo", () => {
  const modelo = armar(GRILLA);
  assert.equal(modelo.celdas.get(clave("r1", "a2")), undefined);
});

test("escribir marca solo la celda tocada", () => {
  const modelo = armar(GRILLA);
  assert.equal(haySinGuardar(modelo), false);
  const editado = escribir(modelo, "r1", GRILLA.insumos[1], "0.02");
  assert.equal(haySinGuardar(editado), true);
  assert.deepEqual(
    cambios(editado).map((c) => [c.receta_id, c.articulo_id, c.expresion]),
    [["r1", "a2", "0.02"]],
  );
});

test("escribir no muta el modelo anterior", () => {
  const modelo = armar(GRILLA);
  escribir(modelo, "r1", GRILLA.insumos[1], "0.02");
  assert.equal(haySinGuardar(modelo), false);
});

test("vaciar una celda viaja como expresión vacía", () => {
  // Es cómo se dice "este insumo no va en esta receta": el servidor borra
  // la línea.
  const editado = escribir(armar(GRILLA), "r1", GRILLA.insumos[0], "");
  assert.equal(cambios(editado)[0].expresion, "");
});

test("solo viaja lo que se tocó", () => {
  const editado = escribir(armar(GRILLA), "r1", GRILLA.insumos[0], "0.2");
  assert.equal(cambios(editado).length, 1);
});

test("el pegado entiende lo que manda Excel", () => {
  assert.deepEqual(leerPegado("1\t2\r\n3\t4\r\n"), [
    ["1", "2"],
    ["3", "4"],
  ]);
  // Una celda vacía en el medio es un tabulador pegado a otro.
  assert.deepEqual(leerPegado("1\t\t3"), [["1", "", "3"]]);
});

test("pegar un rectángulo llena desde el cursor", () => {
  const modelo = pegar(armar(GRILLA), 0, 0, [
    ["0.1", "0.2"],
    ["0.3", "0.4"],
  ]);
  assert.equal(modelo.celdas.get(clave("r1", "a1"))?.texto, "0.1");
  assert.equal(modelo.celdas.get(clave("r2", "a2"))?.texto, "0.4");
  assert.equal(cambios(modelo).length, 4);
});

test("lo que se sale de la grilla se descarta", () => {
  // Pegar cinco filas cuando quedan dos es un accidente común; crecer la
  // grilla sola sería inventar recetas que nadie pidió.
  const modelo = pegar(armar(GRILLA), 1, 1, [
    ["0.1", "0.2", "0.3"],
    ["0.4", "0.5", "0.6"],
  ]);
  assert.equal(modelo.celdas.get(clave("r2", "a2"))?.texto, "0.1");
  assert.equal(cambios(modelo).length, 1);
});

test("pegar acepta operaciones, no solo números", () => {
  const modelo = pegar(armar(GRILLA), 0, 0, [["1000/3"]]);
  assert.equal(cambios(modelo)[0].expresion, "1000/3");
});

test("copiar y volver a pegar da lo mismo", () => {
  const modelo = armar(GRILLA);
  const bloque = leerPegado(copiar(modelo));
  const vuelta = pegar(modelo, 0, 0, bloque);
  assert.equal(vuelta.celdas.get(clave("r2", "a1"))?.texto, "450/3");
});

test("el costo de la columna usa lo que hay en pantalla", () => {
  const modelo = armar(GRILLA);
  // r1 lleva 0.15 kg de queso a 20 = 3
  assert.equal(costo(modelo, "r1", evaluar), 3);
  // r2 lleva "450/3" = 150 kg a 20 = 3000
  assert.equal(costo(modelo, "r2", evaluar), 3000);
});

test("una celda a medio escribir no rompe el costo", () => {
  // "250*" es un borrador, no un error.
  const modelo = escribir(armar(GRILLA), "r1", GRILLA.insumos[1], "250*");
  assert.equal(costo(modelo, "r1", evaluar), 3);
});
