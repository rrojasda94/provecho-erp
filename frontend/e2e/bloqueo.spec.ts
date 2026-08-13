import { expect, test } from "@playwright/test";

import { ADMIN, ingresar, tecleaPin } from "./util";

/**
 * Bloqueo de pantalla del PDV por inactividad (ADR-045, RN-POS-014).
 *
 * Es una prueba de reloj: el plazo real son cinco minutos y esperarlos haría
 * la suite inusable, así que se adelanta el reloj de la página con
 * `page.clock`. Lo que se verifica es lo que distingue este bloqueo de un
 * logout: al desbloquear se sigue en `/pdv` con la misma sesión, no en
 * `/login`.
 */
test("la pantalla se bloquea sola y el PIN la reabre sin cerrar sesión", async ({
  page,
}) => {
  // Antes de navegar: `install()` solo afecta a las cargas siguientes.
  await page.clock.install();
  await ingresar(page, ADMIN);

  await page.goto("/pdv");
  await expect(page.getByTestId("estado-caja")).toBeVisible({ timeout: 30_000 });

  await expect(page.getByRole("heading", { name: "Pantalla bloqueada" })).toBeHidden();

  // Seis minutos sin tocar nada: por encima de los cinco del plazo.
  await page.clock.fastForward("06:00");
  await expect(page.getByRole("heading", { name: "Pantalla bloqueada" })).toBeVisible();

  // Un PIN que no es el de la sesión no abre nada.
  await tecleaPin(page, "bloqueo-pin", "000000");
  await expect(page.getByText("PIN incorrecto.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pantalla bloqueada" })).toBeVisible();

  await tecleaPin(page, "bloqueo-pin", ADMIN.pin);
  await expect(page.getByRole("heading", { name: "Pantalla bloqueada" })).toBeHidden();
  // La sesión nunca se cerró: seguimos en el PDV, no en el login.
  await expect(page).toHaveURL(/\/pdv/);
});
