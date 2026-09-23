import assert from "node:assert/strict";
import { test } from "node:test";

import { MODULOS } from "./modulos.ts";
import { SUBMENUS, destinos, grupoDe, itemActivo, pantallasDe } from "./navegacion.ts";

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
    Object.keys(SUBMENUS).reduce((n, clave) => {
      const modulo = MODULOS.find((m) => m.clave === clave)!;
      return n + pantallasDe(clave).filter((i) => i.href !== modulo.href).length;
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

test("un grupo abre en su primera pestaña", () => {
  for (const items of Object.values(SUBMENUS)) {
    for (const g of items.filter((i) => i.pestanas)) {
      assert.equal(g.href, g.pestanas![0].href, `el grupo "${g.label}" no abre en su primera pestaña`);
    }
  }
});

test("las pestañas de un grupo siguen buscándose en la paleta", () => {
  const hrefs = destinos(["*"]).map((d) => d.href);
  for (const href of ["/inventario/lotes", "/inventario/mermas", "/inventario/categorias"]) {
    assert.ok(hrefs.includes(href), `${href} dejó de aparecer en la paleta`);
  }
});

test("una ficha de detalle cae en el grupo de su listado", () => {
  const items = SUBMENUS.inventario;
  assert.equal(grupoDe(items, "/inventario/devoluciones/abc")?.label, "Movimientos");
  assert.equal(grupoDe(items, "/inventario/lotes")?.label, "Stock");
  assert.equal(grupoDe(items, "/inventario/conteos"), undefined);
});

test("en el sidebar gana la coincidencia más larga, no la primera", () => {
  // "Asientos" es `/contabilidad`: en Caja se marcaban los dos.
  assert.equal(itemActivo(SUBMENUS.contabilidad, "/contabilidad/caja")?.label, "Caja");
  assert.equal(itemActivo(SUBMENUS.contabilidad, "/contabilidad")?.label, "Asientos");
  assert.equal(itemActivo(SUBMENUS.inventario, "/inventario/mermas")?.label, "Movimientos");
  assert.equal(itemActivo(SUBMENUS.inventario, "/otra-cosa"), undefined);
});
