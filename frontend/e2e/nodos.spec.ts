import { expect, test } from "@playwright/test";

import { ADMIN, CAJERO, ingresar } from "./util";

/**
 * Lienzo de nodos de receta (ADR-035).
 *
 * Dos pruebas y no más: el job de e2e ya tarda ~4 min y corre con un solo
 * worker, así que acá entra lo que no se puede verificar de otra forma.
 *
 * 1. **El guard de permiso.** La pantalla vive fuera del shell del módulo
 *    para poder tomar los 100dvh, y con eso pierde el guard de
 *    `ModuloShell`. Lo hace ella, y esta prueba es lo único que impide que
 *    un refactor lo borre en silencio — el resto de la suite no entraría
 *    nunca por esta URL.
 * 2. **Que el rediseño no cambió el comportamiento.** Marcar una resta tiene
 *    que tacharla del plato y sacarla del costo; es la misma verdad que
 *    prueba `lib/nodos.test.ts`, pero pasando por la pantalla.
 *
 * La corrección del pan/zoom no se prueba acá: su matemática la cubre
 * `lib/lienzo.test.ts` sin navegador, y lo que queda —que se vea bien— lo
 * tiene que mirar una persona.
 */

test("el cajero no entra al lienzo, ni por URL directa", async ({ page }) => {
  // El cajero tiene `sales.crear` pero no `sales.gestionar_catalogo`. Al
  // salir del shell, esta pantalla dejó de heredar el gate del módulo: si
  // alguna vez se rompe, se rompe silenciosamente y por eso hay prueba.
  await ingresar(page, CAJERO);

  await page.goto("/catalogo/productos/00000000-0000-0000-0000-000000000001/nodos");
  await expect(page.getByText(/Sin permiso/i)).toBeVisible();
  // Y no se filtra nada del catálogo por el camino del error.
  await expect(page.getByText(/Pizza E2E/)).toHaveCount(0);
});

test("el admin arma un plato y la resta sale del costo", async ({ page }) => {
  await ingresar(page, ADMIN);

  await page.goto("/catalogo/productos");
  await page.getByText(/Pizza E2E/).first().click();
  await page.getByRole("link", { name: /Ver nodos/i }).click();

  // El producto de e2e no tiene presentaciones, así que su único tamaño es
  // él mismo (el "Único" del lienzo) y ya arranca elegido.
  await expect(page.getByRole("button", { name: /Único/ })).toBeVisible({
    timeout: 30_000,
  });
  const costo = page.getByText(/Costo del plato/).locator("xpath=following-sibling::dd");
  await expect(costo).not.toHaveText("S/ 0.00");

  // Quitar el único insumo deja el plato en cero y lo declara aparte: eso es
  // exactamente lo que después NO se descuenta del almacén (RN-PRD-019).
  await page.getByRole("button", { name: "sin Harina E2E" }).click();
  await expect(page.getByText(/No se descuenta \(restas\)/)).toBeVisible();
  await expect(costo).toHaveText("S/ 0.00");
});

test("el admin edita la receta desde el nodo y el costo se mueve", async ({
  page,
}) => {
  // Lo que hace del lienzo una forma de trabajar y no un dibujo: abrir el
  // nodo y cambiarle la receta ahí mismo. La cantidad acepta aritmética y la
  // evalúa el SERVIDOR (RN-COM-024): el navegador manda "0.5*2", no 1.
  await ingresar(page, ADMIN);

  await page.goto("/catalogo/productos");
  await page.getByText(/Pizza E2E/).first().click();
  await page.getByRole("link", { name: /Ver nodos/i }).click();

  const unico = page.locator("button.nodo", { hasText: "Único" });
  await expect(unico).toBeVisible({ timeout: 30_000 });
  await unico.click();

  const cantidad = page.locator(".lienzo-cantidad").first();
  await expect(cantidad).toBeVisible();
  const costo = page.getByText(/Costo del plato/).locator("xpath=following-sibling::dd");

  await page.locator('[role="tab"]', { hasText: "Plato" }).click();
  const antes = await costo.innerText();

  await page.locator('[role="tab"]').last().click();
  await cantidad.fill("0.25*4");
  await cantidad.blur();
  await page.locator('[role="tab"]', { hasText: "Plato" }).click();
  await expect(costo).not.toHaveText(antes);
});
