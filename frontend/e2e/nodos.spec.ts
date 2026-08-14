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

test("el admin crea una opción nueva desde el lienzo y la retira", async ({
  page,
}) => {
  // Las tres cosas que el lienzo prometía y no hacía:
  //  1. los puertos se pueden tomar (con `isConnectable={false}` react-flow
  //     ni siquiera dejaba empezar el arrastre, así que `conectar()` —escrito
  //     y probado— era código inalcanzable);
  //  2. una opción que todavía no existe se crea acá, con su receta, en vez
  //     de mandar a otras dos pantallas antes de poder cablearla;
  //  3. se retira.
  await ingresar(page, ADMIN);

  await page.goto("/catalogo/productos");
  await page.getByText(/Pizza E2E/).first().click();
  await page.getByRole("link", { name: /Ver nodos/i }).click();

  const unico = page.locator("button.nodo", { hasText: "Único" });
  await expect(unico).toBeVisible({ timeout: 30_000 });

  // El puerto se puede tomar: react-flow solo pone `connectable` cuando el
  // `<Handle>` lo admite. Es la regresión exacta, sin depender de un arrastre
  // —que en un canvas con zoom es la prueba más frágil que hay—.
  const nodoUnico = page.locator(".react-flow__node", { hasText: "Único" });
  await expect(
    nodoUnico.locator(".react-flow__handle.source"),
  ).toHaveClass(/connectable/);

  await page.getByRole("button", { name: "+ opción" }).click();
  await page.getByLabel(/Buscar o nombrar uno nuevo/i).fill("Aceituna E2E");
  await page.getByLabel(/^Código$/).fill("AE2E");
  await page.getByRole("button", { name: /Crear .*Aceituna E2E.* y colgarlo/ }).click();

  const comoOpcion = page.locator(".react-flow__node-opcion", {
    hasText: "Aceituna E2E",
  });
  const comoDisponible = page.locator(".react-flow__node-disponible", {
    hasText: "Aceituna E2E",
  });
  await expect(comoOpcion).toBeVisible({ timeout: 15_000 });

  // Retirar es **desvincular**, no borrar: el extra es un producto comercial
  // con su receta y su precio, y sigue existiendo para volver a cablearlo.
  // Por eso el nodo no desaparece — cambia de columna.
  await comoOpcion.hover();
  // `exact`: el nombre accesible del botón del nodo contiene el de su acción,
  // así que sin esto el locator matchea los dos.
  await comoOpcion.getByRole("button", { name: "quitar", exact: true }).click();
  await expect(comoOpcion).toHaveCount(0, { timeout: 15_000 });
  await expect(comoDisponible).toHaveCount(1);
});
