import { expect, test } from "@playwright/test";

/**
 * Recorrido del dinero del sitio de marca (ADR-047/ADR-105): carrito →
 * checkout de invitado → recojo con Izipay → pantalla de pago de prueba →
 * confirmación con número de pedido. Toca todo el circuito real
 * (storefront.pedido_web_confirmado → sales.crear_venta →
 * sales.pedido_web_procesado, esta vez disparado por el webhook de pago), no
 * un mock — mismo criterio que la suite
 * `e2e` del ERP: "el flujo del dinero funciona de punta a punta", nada más.
 *
 * Recojo y no delivery: pedir permiso de geolocalización al navegador en
 * un runner headless es un problema aparte (`context.grantPermissions`) que
 * no hace falta resolver para probar que el checkout — asignación de
 * local, ETA, comprobante, evento hacia `sales` — funciona.
 */

const PRODUCTO = "Pizza Storefront E2E";

test("agregar al carrito y pagar con Izipay (de prueba) un pedido de recojo, como invitado", async ({
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
  // Un invitado no paga en efectivo: se le avisa y se le invita a registrarse.
  await page.getByRole("button", { name: "Efectivo" }).click();
  await expect(page.getByText(/necesitas una cuenta/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirmar pedido" })).toBeDisabled();
  await page.getByRole("button", { name: "Izipay" }).click();

  await page.getByRole("button", { name: "Confirmar pedido" }).click();

  // El pedido espera el pago: primero la pantalla de cobro (de prueba, sin
  // credenciales reales de Izipay).
  await expect(page).toHaveURL(/\/pedido\/[^/]+\/pago\?token=/, { timeout: 30_000 });
  await page.getByRole("button", { name: /Aprobar pago/ }).click();

  // El webhook crea la venta; la página de pago detecta el cambio y avanza.
  await expect(page).toHaveURL(/\/pedido\/[^/]+\?token=/, { timeout: 45_000 });
  await expect(page.getByRole("heading", { name: /confirmado/i })).toBeVisible();
  await expect(page.getByText(/Pedido #\d+/)).toBeVisible();
  await expect(page.getByText(PRODUCTO)).toBeVisible();
});
