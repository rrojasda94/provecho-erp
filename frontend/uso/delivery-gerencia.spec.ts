import { expect, test } from "@playwright/test";

import { ADMIN, contar, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Recorrido: Gerencia pone el precio del delivery por kilómetro.
 *
 * Es el recorrido que no existía y por el cual la función quedó apagada tres
 * meses (ADR-067): la tarifa vivía en el `.env`, así que la única forma de
 * cambiarla era editar el servidor y redesplegar. Lo que se afirma acá es que
 * el número se pone **desde la app**, y que no cobra hasta que se aprueba
 * (ADR-014, RN-GER-009).
 *
 * **Corre sin claves de Google, igual que `direccion.spec.ts`**, y eso
 * también es parte de lo que se prueba: la pantalla tiene que *decir* que
 * faltan. Esa es toda la diferencia entre «no está construido» y «falta una
 * clave», que es la confusión que originó este cambio.
 */

const BASE = "7.50";
const POR_KM = "1.20";

test("la tarifa del delivery se fija y se aprueba desde Gerencia", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /^Gerencia/ }).click();
  await page.locator("aside").getByRole("link", { name: "Delivery" }).click();
  await expect(page.getByRole("heading", { name: "Tarifa del delivery" })).toBeVisible();

  // Sin claves de Google la pantalla lo dice en vez de aparentar que anda.
  await expect(page.getByText(/GOOGLE_MAPS_SERVER_KEY/)).toBeVisible();
  await expect(page.getByText(/GOOGLE_MAPS_BROWSER_KEY/)).toBeVisible();
  // Y de fábrica el reparto no se cobra: los tres valores están en cero.
  await expect(page.getByText(/no se está cobrando/)).toBeVisible();
  await capturar(page, testInfo, "delivery-apagado");

  await page.getByLabel("Tarifa base (S/)").fill(BASE);
  await page.getByLabel("Precio por kilómetro (S/)").fill(POR_KM);
  await page.getByLabel("Radio máximo (km)").fill("8");
  await page.getByLabel("Distritos sin reparto propio").fill("Belén");
  await page.getByRole("button", { name: "Proponer cambio" }).click();

  // Propuesto ≠ vigente: hasta que Gerencia aprueba, el PDV sigue cobrando lo
  // de antes. Es el mecanismo entero de ADR-014.
  const pendientes = page.getByRole("listitem").filter({ hasText: "Precio por kilómetro" });
  await expect(pendientes).toBeVisible();
  await expect(page.getByText(/no se está cobrando/)).toBeVisible();
  await capturar(page, testInfo, "delivery-propuesto");

  for (const rotulo of [
    "Tarifa base",
    "Precio por kilómetro",
    "Radio máximo",
    "Distritos sin reparto propio",
  ]) {
    await page
      .getByRole("listitem")
      .filter({ hasText: rotulo })
      .getByRole("button", { name: "Aprobar" })
      .click();
    await expect(
      page.getByRole("listitem").filter({ hasText: rotulo }),
    ).toHaveCount(0);
  }

  // Recién ahora la tarifa es la que cobra el PDV.
  await expect(page.getByText(`S/ ${BASE} de base`)).toBeVisible();
  await expect(page.getByText(`S/ ${POR_KM} por km`)).toBeVisible();
  await expect(page.getByLabel("Tarifa base (S/)")).toHaveValue(BASE);
  await capturar(page, testInfo, "delivery-vigente");
});


/**
 * La otra mitad: que el número puesto arriba **se cobre**.
 *
 * Corre después del anterior a propósito —Playwright respeta el orden del
 * archivo y la suite usa un solo worker—, contra la tarifa que ese acaba de
 * dejar vigente. Es la deuda que ADR-054 declaró y que desde caja se leía
 * como que el PDV estaba roto: el cajero veía «reparto S/ 7.50» y el ticket
 * cobraba el subtotal pelado (RN-COM-040).
 *
 * La dirección se escribe **a mano**: sin clave de Maps no hay ancla, no hay
 * distancia que medir, y aun así hay tarifa base que cobrar. Es el caso que
 * más se va a dar en producción hasta que las claves estén puestas, y el que
 * hacía que la pantalla mintiera.
 */
const PRODUCTO = "Pizza E2E";

test("el ticket del PDV cobra el reparto", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/pdv");

  // No se cobra sin caja abierta, ni siquiera un delivery (ADR-025). El PDV
  // abre solo el diálogo de apertura cuando no la hay; puede venir abierta de
  // otro recorrido —la caja es del punto de venta y la suite corre con un
  // worker— o de una corrida anterior sobre la misma base.
  const caja = page.getByTestId("estado-caja");
  await expect(caja).toBeVisible({ timeout: 30_000 });
  if ((await caja.textContent())?.includes("cerrada")) {
    await contar(page, { "100": 1 });
    await dialogo(page).getByTestId("apertura-declarado").fill("100");
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
  }
  await expect(caja).toContainText("Caja abierta", { timeout: 30_000 });

  await page.getByRole("button", { name: new RegExp(PRODUCTO, "i") }).first().click();
  await dialogo(page).getByRole("button", { name: /Guardar/i }).click();

  await page.getByRole("button", { name: /^Cobrar$/i }).click();
  await expect(dialogo(page).getByText("Tipo de orden")).toBeVisible();
  await dialogo(page).getByRole("button", { name: /Delivery/i }).click();
  await dialogo(page).getByLabel("Dirección de entrega").fill("Jr. Lima 200");
  // Sin ancla no hay kilómetros, pero sí tarifa base: el servidor la cotiza
  // igual y el cajero tiene que verla antes de aceptar.
  await expect(dialogo(page).getByText(/Reparto S\/ 7\.50/)).toBeVisible();
  await capturar(page, testInfo, "pdv-cotizacion");
  await dialogo(page).getByRole("button", { name: /^Confirmar$/ }).click();

  // Y el ticket lo suma en su propia fila, no repartido entre las líneas.
  await expect(page.getByText("Reparto", { exact: true })).toBeVisible();
  await expect(page.getByText("S/ 7.50", { exact: true })).toBeVisible();
  await capturar(page, testInfo, "pdv-ticket-con-reparto");
});
