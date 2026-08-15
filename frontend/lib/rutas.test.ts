import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { MODULOS } from "./modulos.ts";
import { SUBMENUS } from "./navegacion.ts";

/**
 * `navegacion.test.ts` comprueba que MODULOS y SUBMENUS concuerden entre sí,
 * pero los dos pueden estar de acuerdo apuntando a una ruta que no existe: eso
 * fue lo que dejó viva durante semanas la deuda "7 íconos del home llevan a
 * 404" sin que nadie pudiera decir si seguía siendo cierta. Acá se resuelve
 * contra el árbol de archivos, que es la única fuente que no miente.
 */

const APP = join(dirname(fileURLToPath(import.meta.url)), "..", "app");

/** Rutas reales del router: un `page.tsx` es una ruta, una carpeta entre
 * paréntesis es un grupo y no aporta segmento. */
function rutas(dir: string, prefijo = ""): string[] {
  const encontradas: string[] = [];
  for (const entrada of readdirSync(dir, { withFileTypes: true })) {
    if (entrada.isFile() && entrada.name === "page.tsx") {
      encontradas.push(prefijo === "" ? "/" : prefijo);
      continue;
    }
    if (!entrada.isDirectory() || entrada.name === "api") continue;
    const grupo = entrada.name.startsWith("(") && entrada.name.endsWith(")");
    encontradas.push(...rutas(join(dir, entrada.name), grupo ? prefijo : `${prefijo}/${entrada.name}`));
  }
  return encontradas;
}

const REALES = rutas(APP);

/** `/inventario/skus/[id]` cubre `/inventario/skus/algo`. */
function existe(href: string): boolean {
  const partes = href.split("/");
  return REALES.some((ruta) => {
    const suyas = ruta.split("/");
    return (
      suyas.length === partes.length &&
      suyas.every((seg, i) => seg === partes[i] || seg.startsWith("["))
    );
  });
}

test("cada ícono del home lleva a una pantalla que existe", () => {
  for (const modulo of MODULOS) {
    assert.ok(existe(modulo.href), `el módulo "${modulo.clave}" apunta a ${modulo.href}, que no existe`);
  }
});

test("cada ítem de submenú lleva a una pantalla que existe", () => {
  for (const [clave, items] of Object.entries(SUBMENUS)) {
    for (const item of items) {
      assert.ok(existe(item.href), `"${clave} → ${item.label}" apunta a ${item.href}, que no existe`);
    }
  }
});

test("ninguna raíz de módulo se redirige a sí misma", () => {
  // Las raíces que redirigen mandan a `modulo.href`. Si ese href fuera la
  // propia raíz, la redirección se llamaría a sí misma: el navegador corta con
  // un error que no nombra ni el módulo ni el archivo que lo causó.
  for (const modulo of MODULOS) {
    const raiz = `/${modulo.href.split("/")[1]}`;
    const archivo = join(APP, "(app)", raiz.slice(1), "page.tsx");
    if (!existsSync(archivo)) continue;
    if (!readFileSync(archivo, "utf8").includes("redirect(")) continue;
    assert.notEqual(modulo.href, raiz, `la raíz ${raiz} redirige a sí misma`);
  }
});
