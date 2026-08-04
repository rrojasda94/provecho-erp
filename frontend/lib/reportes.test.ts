/**
 * Checks de la lógica no trivial del tablero: escapado CSV y reordenamiento
 * de tarjetas. Corre con `npm run test:reportes` — `node:test` y el soporte
 * de TypeScript vienen en Node 22+, no hay framework que instalar.
 */

import assert from "node:assert/strict";
import test from "node:test";

// Extensión explícita: Node resuelve ESM por ruta real, no por convención de
// bundler (el resto del frontend importa sin extensión, vía Next/tsc).
import { aCsv, nombreArchivo, reordenar, type Columna } from "./reportes-datos.ts";

const COLUMNAS: Columna[] = [
  { clave: "proveedor", titulo: "Proveedor", tipo: "texto" },
  { clave: "total", titulo: "Total", tipo: "dinero" },
];

test("el CSV lleva cabecera y una fila por dato", () => {
  const csv = aCsv(COLUMNAS, [{ proveedor: "Molinos SAC", total: "6720.00" }]);
  assert.equal(csv, "Proveedor,Total\r\nMolinos SAC,6720.00");
});

test("una coma en el dato no parte la fila en dos columnas", () => {
  const csv = aCsv(COLUMNAS, [{ proveedor: "Molinos SAC, EIRL", total: "1.00" }]);
  assert.equal(csv, 'Proveedor,Total\r\n"Molinos SAC, EIRL",1.00');
});

test("las comillas internas se duplican (RFC 4180)", () => {
  const csv = aCsv(COLUMNAS, [{ proveedor: 'El "Rey" SAC', total: "1.00" }]);
  assert.equal(csv, 'Proveedor,Total\r\n"El ""Rey"" SAC",1.00');
});

test("un salto de línea en el dato queda dentro del campo entrecomillado", () => {
  const csv = aCsv(COLUMNAS, [{ proveedor: "Linea1\nLinea2", total: "1.00" }]);
  assert.equal(csv, 'Proveedor,Total\r\n"Linea1\nLinea2",1.00');
});

test("un valor nulo sale como campo vacío, no como 'null'", () => {
  const csv = aCsv(COLUMNAS, [{ proveedor: "Sin costo", total: null }]);
  assert.equal(csv, "Proveedor,Total\r\nSin costo,");
});

test("el CSV exporta las columnas declaradas, no las claves de la fila", () => {
  // `receta_id` es dato interno del cruce: si se colara en la fila, no debe
  // terminar en el archivo que alguien abre en Excel.
  const csv = aCsv(COLUMNAS, [
    { proveedor: "X", total: "1.00", receta_id: "no-deberia-salir" },
  ]);
  assert.equal(csv.includes("no-deberia-salir"), false);
});

const DATOS = { codigo: "x", desde: "2026-07-06", hasta: "2026-08-04", columnas: [], filas: [] };

test("el nombre de archivo sale sin tildes ni espacios", () => {
  assert.equal(
    nombreArchivo("Ventas por día", DATOS),
    "ventas-por-dia_2026-07-06_2026-08-04.csv",
  );
});

test("el nombre de archivo no empieza ni termina en guion", () => {
  assert.equal(nombreArchivo("¿Margen?", DATOS), "margen_2026-07-06_2026-08-04.csv");
});

test("reordenar mueve la tarjeta a la posición pedida", () => {
  assert.deepEqual(reordenar(["a", "b", "c"], 0, 2), ["b", "c", "a"]);
  assert.deepEqual(reordenar(["a", "b", "c"], 2, 0), ["c", "a", "b"]);
});

test("reordenar no muta el array original", () => {
  const original = ["a", "b", "c"];
  reordenar(original, 0, 2);
  assert.deepEqual(original, ["a", "b", "c"]);
});

test("reordenar con índices inválidos devuelve la lista intacta", () => {
  // `findIndex` devuelve -1 si el uid arrastrado ya no está: soltar sobre
  // una tarjeta recién quitada no puede romper el tablero.
  const original = ["a", "b", "c"];
  assert.equal(reordenar(original, -1, 1), original);
  assert.equal(reordenar(original, 1, -1), original);
  assert.equal(reordenar(original, 0, 99), original);
  assert.equal(reordenar(original, 1, 1), original);
});
