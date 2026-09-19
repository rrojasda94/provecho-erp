import { expect, test } from "@playwright/test";

/**
 * Armar una Mitad x Mitad con un extra en el sitio (ADR-105, RN-WEB-017), pagarla
 * con Izipay de prueba y ver en el pedido lo que se eligió. Toca todo el camino
 * de las opciones: carta pública con opciones → carrito con líneas distintas →
 * checkout → pedido pendiente hasta el webhook → venta con sus extras.
 */

const PIZZA = "Pizza Mitad E2E";

test("armar una Mitad x Mitad con extra y pagarla con Izipay (de prueba)", async ({ page }) => {
  await page.goto("/carta");
  await page.getByRole("link", { name: new RegExp(PIZZA) }).click();
  await expect(page.getByRole("heading", { name: PIZZA })).toBeVisible();

  // Sin elegir las dos mitades no se puede agregar.
  const agregar = page.getByRole("button", { name: /Agregar/ });
  await expect(agregar).toBeDisabled();
  await expect(page.getByText("Elige Mitad 1")).toBeVisible();

  const mitad1 = page.getByRole("group", { name: "Mitad 1" });
  const mitad2 = page.getByRole("group", { name: "Mitad 2" });
  await mitad1.getByRole("button", { name: /Hawaiana/ }).click();
  // El mismo sabor en las dos mitades no es una mitad y mitad: ya no se ofrece.
  await expect(mitad2.getByRole("button", { name: "Hawaiana" })).toBeDisabled();
  await mitad2.getByRole("button", { name: "Peperoni" }).click();
  await expect(agregar).toBeEnabled();
  await expect(agregar).toContainText("43.00"); // 40 + 3 de la Hawaiana

  await page
    .getByRole("group", { name: /Agrega extras/ })
    .getByRole("button", { name: "Más" })
    .click();
  await expect(agregar).toContainText("49.00"); // + 6 del extra queso
  await agregar.click();
  await expect(page.getByRole("button", { name: "¡Agregado!" })).toBeVisible();

  await page.goto("/carrito");
  await expect(page.getByText("Mitad 1: Hawaiana")).toBeVisible();
  await expect(page.getByText("1× Extra Queso E2E")).toBeVisible();
  await expect(page.getByText("S/ 49.00").first()).toBeVisible();

  await page.goto("/checkout");
  await expect(page.getByRole("heading", { name: "Checkout" })).toBeVisible();
  await page.getByRole("button", { name: "Recojo en local" }).click();
  await expect(page.locator("select")).toBeVisible();
  await page.getByPlaceholder("Tu nombre").fill("Cliente Mitad");
  await page.getByPlaceholder("Teléfono").fill("987654321");
  await page.getByRole("button", { name: "Izipay" }).click();
  await page.getByRole("button", { name: "Confirmar pedido" }).click();

  await expect(page).toHaveURL(/\/pedido\/[^/]+\/pago\?token=/, { timeout: 30_000 });
  await page.getByRole("button", { name: /Aprobar pago/ }).click();
  await expect(page).toHaveURL(/\/pedido\/[^/]+\?token=/, { timeout: 45_000 });

  // El pedido muestra lo que se eligió y cobra lo mismo que la carta.
  await expect(page.getByRole("heading", { name: /confirmado/i })).toBeVisible();
  await expect(page.getByText("Hawaiana + Peperoni")).toBeVisible();
  await expect(page.getByText("1× Extra Queso E2E")).toBeVisible();
  await expect(page.getByText("S/ 49.00").first()).toBeVisible();
});
