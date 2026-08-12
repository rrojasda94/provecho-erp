import { expect, test } from "@playwright/test";

import { ADMIN, CAJERO, ingresar } from "./util";

/**
 * Sesión y permisos visuales: los dos casos que la estrategia de pruebas
 * (`docs/engineering/testing-strategy.md`) da por justificados además del
 * flujo del dinero.
 *
 * 1. **Que la sesión funcione.** Si el login, la cookie o el guard se
 *    rompen, no importa qué más ande — y ninguna de las tres piezas vive
 *    entera de un solo lado: la cookie la pone una Server Action, el guard
 *    corre en el servidor y el redirect lo resuelve el cliente.
 * 2. **El gate de módulo por permiso** (ADR-013 y su enmienda de
 *    2026-08-03). Es el único caso donde *ver* ya es el privilegio, y el
 *    filtro del home es solo UX: lo que decide es el `layout.tsx`. Probarlo
 *    entrando por URL directa es la única forma de verificar que el guard
 *    real está puesto y no solo el filtro cosmético.
 *
 * Sin `serial` a propósito: ninguna de estas pruebas toca el estado de la
 * caja ni deja rastro en la base, así que no se pasan nada entre ellas.
 */

test("una ruta protegida sin sesión manda al login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeVisible();
});

test("el login deja el token en una cookie httpOnly y el logout la borra", async ({
  page,
  context,
}) => {
  await ingresar(page, ADMIN);

  const token = (await context.cookies()).find((c) => c.name === "provecho_token");
  expect(token).toBeDefined();
  // `httpOnly` es la razón de ser de esta prueba: un token legible por
  // `document.cookie` lo roba cualquier XSS, y es un atributo que no se ve
  // en ninguna pantalla — se rompe en silencio.
  expect(token?.httpOnly).toBe(true);

  // Salir dejó de ser un botón suelto en la barra: vive en el menú de la
  // sesión, junto a las preferencias de presentación.
  await page.getByRole("button", { name: new RegExp(`Sesión de ${ADMIN.usuario}`, "i") }).click();
  await page.getByRole("menuitem", { name: /Cerrar sesión/i }).click();
  await expect(page).toHaveURL(/\/login/);

  // Y la sesión quedó realmente muerta, no solo la pantalla cambiada.
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

test("el cajero no ve Catálogo, ni entrando por URL", async ({ page }) => {
  // El cajero tiene `sales.crear`/`sales.cobrar` pero no
  // `sales.gestionar_catalogo`: con el filtro por prefijo veía y leía toda
  // la carta. Administrarla es acto de supervisor, no de quien vende con
  // ella.
  await ingresar(page, CAJERO);

  await expect(page.getByRole("link", { name: /Ventas/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Catálogo/i })).toHaveCount(0);

  await page.goto("/catalogo/productos");
  await expect(page.getByText(/Sin permiso/i)).toBeVisible();
  await expect(page.getByText(/Pizza E2E/)).toHaveCount(0);
});

test("el admin sí ve Catálogo y lo puede abrir", async ({ page }) => {
  // La contraparte del caso anterior: sin esto, un gate que esconde el
  // módulo para *todos* pasaría por bueno.
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /Catálogo/i }).click();
  await expect(page.getByText(/Sin permiso/i)).toHaveCount(0);
  await expect(page.getByText(/Pizza E2E/).first()).toBeVisible({ timeout: 30_000 });
});
