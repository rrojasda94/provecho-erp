import { expect, test } from "@playwright/test";

/**
 * Recorrido del dinero del sitio de marca (ADR-047/ADR-105): carrito →
 * checkout de invitado → recojo en efectivo → confirmación con número de
 * pedido. Es el caso más simple que igual toca todo el circuito real
 * (storefront.pedido_web_confirmado → sales.crear_venta →
 * sales.pedido_web_procesado), no un mock — mismo criterio que la suite
 * `e2e` del ERP: "el flujo del dinero funciona de punta a punta", nada más.
 *
 * Recojo y no delivery: pedir permiso de geolocalización al navegador en
 * un runner headless es un problema aparte (`context.grantPermissions`) que
 * no hace falta resolver para probar que el checkout — asignación de
 * local, ETA, comprobante, evento hacia `sales` — funciona.
 */

const PRODUCTO = "Pizza Storefront E2E";

test("agregar al carrito y confirmar un pedido de recojo en efectivo, como invitado", async ({
  page,
}) => {
  await page.goto("/carta");
  await expect(page.getByRole("heading", { name: "Carta" })).toBeVisible();

  await page.getByRole("link", { name: new RegExp(PRODUCTO) }).click();
  await expect(page.getByRole("heading", { name: PRODUCTO })).toBeVisible();
  await page.getByRole("button", { name: /Agregar/ }).click();
  await expect(page.getByRole("button", { name: "¡Agregado!" })).toBeVisible();

  await page.goto("/checkout");
  await expect(page.getByRole("heading", { name: "Checkout" })).toBeVisible();

  await page.getByRole("button", { name: "Recojo en local" }).click();
  // El único `<select>` del formulario en esta modalidad es el de local.
  await expect(page.locator("select")).toBeVisible();

  await page.getByPlaceholder("Tu nombre").fill("Cliente E2E");
  await page.getByPlaceholder("Teléfono").fill("987654321");
  await page.getByRole("button", { name: "Efectivo" }).click();

  await page.getByRole("button", { name: "Confirmar pedido" }).click();

  // La confirmación es síncrona (el bus de eventos es en proceso): sin
  // polling, se espera la URL de destino directo.
  await expect(page).toHaveURL(/\/pedido\/.+token=/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: /confirmado/i })).toBeVisible();
  await expect(page.getByText(/Pedido #\d+/)).toBeVisible();
  await expect(page.getByText(PRODUCTO)).toBeVisible();
});
