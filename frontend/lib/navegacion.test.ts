import assert from "node:assert/strict";
import { test } from "node:test";

import { MODULOS } from "./modulos.ts";
import { SUBMENUS, destinos } from "./navegacion.ts";

/** Lo que la paleta de comandos ofrece sale de acá. Un error en este archivo
 * no rompe nada visible: simplemente una pantalla deja de poder buscarse, o
 * peor, aparece para quien no debería verla. */

test("cada clave de SUBMENUS corresponde a un módulo registrado", () => {
  const claves = new Set(MODULOS.map((m) => m.clave));
  for (const clave of Object.keys(SUBMENUS)) {
    assert.ok(claves.has(clave), `SUBMENUS tiene "${clave}", que no está en MODULOS`);
  }
});

test("el comodín ve todos los módulos y todas sus pantallas", () => {
  const encontrados = destinos(["*"]);
  const esperados =
    MODULOS.length +
    Object.entries(SUBMENUS).reduce((n, [clave, items]) => {
      const modulo = MODULOS.find((m) => m.clave === clave)!;
      return n + items.filter((i) => i.href !== modulo.href).length;
    }, 0);
  assert.equal(encontrados.length, esperados);
});

test("no ofrece pantallas de módulos sin permiso", () => {
  const encontrados = destinos(["purchases.leer"]);
  assert.ok(encontrados.length > 0);
  assert.ok(
    encontrados.every((d) => d.href.startsWith("/compras")),
    `se coló algo ajeno a compras: ${encontrados.map((d) => d.href).join(", ")}`,
  );
});

test("sin permisos no ofrece nada", () => {
  assert.deepEqual(destinos([]), []);
});

test("ningún destino aparece dos veces", () => {
  // La entrada del módulo apunta a su primera pantalla, que además está en su
  // submenú: sin filtrar, buscar "compras" devolvía dos filas idénticas.
  const hrefs = destinos(["*"]).map((d) => d.href);
  assert.equal(new Set(hrefs).size, hrefs.length);
});

test("cada destino trae la clave de un módulo real", () => {
  // Si la clave no resuelve, la paleta intenta renderizar `undefined` como
  // componente y la pantalla entera cae.
  const claves = new Set(MODULOS.map((m) => m.clave));
  for (const d of destinos(["*"])) {
    assert.ok(claves.has(d.clave), `destino ${d.href} apunta a la clave "${d.clave}"`);
  }
});
