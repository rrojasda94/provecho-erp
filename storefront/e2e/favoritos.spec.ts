import { expect, test } from "@playwright/test";

/**
 * El corazón de la carta se marca **y se desmarca**, y sigue como quedó
 * después de recargar.
 *
 * El circuito completo no tenía ninguna prueba. La del caso que lo rompió en
 * el sitio real —desincronizar la lista y que el servidor rechace el segundo
 * toque— vive en `tests/test_storefront_cuentas.py::test_favoritos_crud`,
 * donde se puede provocar; acá se cubre que el camino feliz exista.
 */

/** Cuenta nueva por corrida: el favorito es de la cuenta, no del navegador. */
async function crearCuenta(page: import("@playwright/test").Page) {
  const sufijo = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  await page.goto("/cuenta/registro");
  await page.getByPlaceholder("Nombres").fill("Fabiana");
  await page.getByPlaceholder("Apellidos").fill("Prueba");
  await page.getByPlaceholder("Email").fill(`fav-${sufijo}@example.com`);
  await page.getByPlaceholder("Clave (mínimo 8 caracteres)").fill("clave-de-prueba");
  await page.getByPlaceholder("DNI").fill(String(10000000 + (Date.now() % 80000000)));
  await page.getByPlaceholder("Teléfono").fill("999111222");
  await page.locator('input[name="fecha_nacimiento"]').fill("1995-03-12");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page).toHaveURL(/\/cuenta$/);
}

test("marcar y desmarcar un favorito", async ({ page }) => {
  await crearCuenta(page);

  await page.goto("/carta");
  await page.getByTitle("Agregar a favoritos").first().click();
  await expect(page.getByTitle("Quitar de favoritos")).toHaveCount(1);

  // Desmarcar, que es lo que no funcionaba.
  await page.getByTitle("Quitar de favoritos").first().click();
  await expect(page.getByTitle("Quitar de favoritos")).toHaveCount(0);

  // Y sigue desmarcado al recargar: el estado es del servidor, no de la pantalla.
  await page.reload();
  await expect(page.getByTitle("Quitar de favoritos")).toHaveCount(0);
});
