import assert from "node:assert/strict";
import test from "node:test";

import { type Pagina, leerPagina, recorrerPaginas, rutaPagina } from "./api.ts";

/** Un listado de `total` filas servido de a `tamano`, como la API. */
function servidor(total: number, tamano: number) {
  const pedidas: number[] = [];
  const pedir = async (page: number): Promise<Pagina<number>> => {
    pedidas.push(page);
    const desde = (page - 1) * tamano;
    const items = Array.from({ length: Math.max(0, Math.min(tamano, total - desde)) }, (_, i) => desde + i);
    return { items, total, page, page_size: tamano };
  };
  return { pedir, pedidas };
}

test("pasa de la fila 200: trae todas las páginas", async () => {
  const { pedir, pedidas } = servidor(450, 200);
  const filas = await recorrerPaginas(pedir);
  assert.equal(filas.length, 450);
  assert.equal(filas.at(-1), 449);
  assert.deepEqual(pedidas, [1, 2, 3]);
});

test("un listado vacío es una sola petición", async () => {
  const { pedir, pedidas } = servidor(0, 200);
  assert.deepEqual(await recorrerPaginas(pedir), []);
  assert.deepEqual(pedidas, [1]);
});

test("si el total crece entre páginas no se queda en un bucle", async () => {
  // Una página vacía corta aunque `total` diga que falta: alguien borró
  // filas mientras se recorría.
  const pedir = async (page: number): Promise<Pagina<number>> =>
    page === 1 ? { items: [1], total: 5, page, page_size: 200 } : { items: [], total: 5, page, page_size: 200 };
  assert.deepEqual(await recorrerPaginas(pedir), [1]);
});

test("rutaPagina conserva los filtros y pisa la paginación", () => {
  assert.equal(
    rutaPagina("/api/v1/inventory/articulos?tipo=insumo&page_size=50", 3),
    "/api/v1/inventory/articulos?tipo=insumo&page_size=200&page=3",
  );
  assert.equal(rutaPagina("/api/v1/users", 1), "/api/v1/users?page=1&page_size=200");
});

test("leerPagina acota lo que llega por la URL", () => {
  const { query, pagina, tamano, q } = leerPagina({ q: "  harina ", page: "-3", page_size: "9999" });
  assert.equal(pagina, 1);
  assert.equal(tamano, 200);
  assert.equal(q, "harina");
  assert.equal(query.toString(), "page=1&page_size=200&q=harina");
  assert.equal(leerPagina({ page: "abc" }).tamano, 50);
});
