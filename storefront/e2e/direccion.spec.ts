import { expect, test } from "@playwright/test";

/**
 * El campo de dirección del checkout **sin clave de Google** (que es como
 * corre CI y como corre el sitio si alguien se olvida la clave en el `.env`).
 *
 * Lo que se protege acá es la degradación: el campo tiene que seguir siendo un
 * `<input>` común —ni `role="combobox"`, ni mapa, ni desplegable— y el sitio
 * tiene que decir con todas las letras que sin punto en el mapa no se puede
 * cotizar un delivery, en vez de dejar el botón apagado sin explicación.
 *
 * El camino con clave (sugerencias de Google, pin arrastrable) no se puede
 * probar acá: depende de un tercero y se cobra por llamada.
 */
test("sin clave de Google el campo sigue siendo un input y el delivery lo explica", async ({
  page,
}) => {
  // Producto sin sabores que elegir: acá lo que se prueba es la dirección.
  await page.goto("/carta");
  await page.getByRole("link", { name: /Pizza Storefront E2E/ }).click();
  await page.getByRole("button", { name: /^Agregar —/ }).click();
  await expect(page.getByRole("button", { name: /¡Agregado!/ })).toBeVisible();
  await page.goto("/checkout");

  // Delivery viene elegido por defecto.
  const campo = page.locator('input[name="direccion"]');
  await expect(campo).toBeVisible();
  await expect(campo).not.toHaveAttribute("role", "combobox");
  await expect(page.getByText("El mapa no está disponible.")).toBeVisible();

  // Los cinco campos del ancla existen y van vacíos.
  await expect(page.locator('input[name="ubicacion_lat"]')).toHaveValue("");

  await campo.fill("Jr. Lima 123");
  await page.getByPlaceholder("Tu nombre").fill("Fabiana");
  await page.getByPlaceholder("Teléfono").fill("999111222");
  await page.getByRole("button", { name: "Confirmar pedido" }).click();

  await expect(page.getByText(/necesitamos el punto en el mapa/)).toBeVisible();
});
