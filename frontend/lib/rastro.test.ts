import assert from "node:assert/strict";
import { test } from "node:test";

import { padreDe, rastroDe } from "./rastro.ts";

const etiquetas = (pathname: string, hoja?: string) =>
  rastroDe(pathname, hoja).map((m) => m.label);

test("la ficha muestra el camino entero hasta lo que se está viendo", () => {
  assert.deepEqual(etiquetas("/inventario/lotes/abc-123", "Lote L-2026-04"), [
    "Inicio",
    "Inventario",
    "Lotes",
    "Lote L-2026-04",
  ]);
});

test("una sección que NO es la pantalla de entrada del módulo sí aparece", () => {
  // El módulo se resuelve por el primer tramo de la ruta. Comparando contra
  // `modulo.href` —que es `/inventario/articulos`, su primera pantalla—
  // `/inventario/lotes` no pertenecía a ningún módulo y el rastro quedaba en
  // "Inicio".
  assert.deepEqual(etiquetas("/inventario/lotes"), ["Inicio", "Inventario", "Lotes"]);
});

test("la sección que ES la pantalla de entrada no se repite", () => {
  // Inventario abre en Artículos: dos migas seguidas al mismo destino.
  assert.deepEqual(etiquetas("/inventario/articulos/abc", "Harina 000"), [
    "Inicio",
    "Inventario",
    "Harina 000",
  ]);
});

test("gana la sección con el prefijo más largo, no la primera que coincide", () => {
  // `/contabilidad` (Asientos) es prefijo de `/contabilidad/caja`: tomando la
  // primera coincidencia, toda pantalla de contabilidad diría "Asientos".
  assert.deepEqual(etiquetas("/contabilidad/caja"), ["Inicio", "Contabilidad", "Caja"]);
});

test("la sección que es el módulo no se repite", () => {
  // El sidebar de contabilidad arranca en "Asientos", que ES `/contabilidad`.
  assert.deepEqual(etiquetas("/contabilidad"), ["Inicio", "Contabilidad"]);
});

test("una ruta que no pertenece a ningún módulo no inventa niveles", () => {
  assert.deepEqual(etiquetas("/pdv"), ["Inicio"]);
  assert.deepEqual(etiquetas("/loquesea", "Algo"), ["Inicio", "Algo"]);
});

test("un prefijo no es un módulo: /inventariado no es /inventario", () => {
  assert.deepEqual(etiquetas("/inventariado"), ["Inicio"]);
});

test("el padre es el nivel de arriba, y nunca se sale de la app", () => {
  assert.equal(
    padreDe(rastroDe("/inventario/articulos/abc-123", "Harina 000")),
    "/inventario/articulos",
  );
  assert.equal(padreDe(rastroDe("/inventario/lotes/abc", "L-1")), "/inventario/lotes");
  assert.equal(padreDe(rastroDe("/")), "/");
});
