import { expect, test } from "@playwright/test";

import { ADMIN, contar, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Los dos hallazgos del turno de prueba que solo se ven armando un pedido de
 * verdad (ADR-074, ADR-075).
 *
 * 1. **El aumento se confirma.** Marcar un producto sobre una mesa ya
 *    abierta lo mandaba a cocina en el acto, dentro de la misma pastilla del
 *    pedido original: el mesero no podía armar tres platos y mandarlos
 *    juntos, y el cocinero no distinguía lo que acababa de entrar.
 * 2. **El borrador sobrevive a recargar.** Vivía en `useState`: un F5 —o una
 *    tablet que se queda sin batería— borraba las pestañas de pedido.
 *
 * Va en `uso/` y no en `e2e/`: el techo de la suite obligatoria son tres
 * cosas y ninguna es esta (`docs/engineering/testing-strategy.md`). Acá el
 * entregable es además la secuencia de capturas — es el recorrido que hay
 * que mostrarle al turno para que reconozca su propio problema arreglado.
 */

const PRODUCTO = "Pizza E2E";
const ESTACION = "Cocina E2E";

/** El PDV no muestra la carta sin caja abierta (ADR-025), y la caja es del
 * punto de venta: puede venir abierta de otro recorrido de esta misma suite.
 * Mismo patrón que `pdv-mitad-y-mitad.spec.ts`. */
async function conCajaAbierta(page: import("@playwright/test").Page) {
  const caja = page.getByTestId("estado-caja");
  await expect(caja).toBeVisible({ timeout: 30_000 });
  if ((await caja.textContent())?.includes("cerrada")) {
    await contar(page, { "100": 1, "50": 2 });
    await dialogo(page).getByTestId("apertura-declarado").fill("200");
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
  }
  await expect(caja).toContainText("Caja abierta", { timeout: 30_000 });
}

/** Marca un producto de la carta y confirma su diálogo. */
async function marcar(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: new RegExp(PRODUCTO, "i") }).first().click();
  await expect(dialogo(page)).toBeVisible();
  await dialogo(page).getByRole("button", { name: "Guardar" }).click();
}

test("el aumento a una orden abierta se confirma y sale como comanda propia", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/pdv");
  await conCajaAbierta(page);

  // Pestaña nueva a propósito: los borradores viven en el servidor y son del
  // punto de venta (ADR-074), así que el PDV abre con lo que dejó el
  // recorrido anterior — y sobre una orden ya enviada no hay tipo que elegir.
  await page.getByRole("button", { name: "Nuevo pedido" }).click();
  await page.getByRole("button", { name: "Tipo de orden" }).click();
  await dialogo(page).getByRole("button", { name: /Para llevar/ }).click();
  await dialogo(page).getByRole("button", { name: "Confirmar" }).click();

  // Antes de enviar, la línea está marcada como pendiente. Es lo que le dice
  // al mesero que todavía tiene algo que confirmar.
  await marcar(page);
  await expect(page.getByText("Sin enviar")).toBeVisible();
  await capturar(page, testInfo, "linea-sin-enviar");

  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Enviado" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Sin enviar")).toBeHidden();

  // El número queda fijo en la cabecera del ticket y es con lo que después se
  // acota la búsqueda en cocina: la cola de la estación es de la sucursal, y
  // esta suite deja pedidos de otros recorridos ahí.
  const cabecera = await page.locator(".pdv-ticket-cab h2").textContent();
  const numero = cabecera?.match(/#(\d+)/)?.[1];
  expect(numero).toBeTruthy();

  // El aumento: marcar un segundo producto **no** lo manda a cocina. Este es
  // el bug — antes salía solo, en el acto, sin que nadie confirmara.
  await marcar(page);
  await expect(page.getByText("Sin enviar")).toBeVisible();
  const enviarAumento = page.getByRole("button", { name: /Enviar aumento \(1\)/ });
  await expect(enviarAumento).toBeEnabled();
  await capturar(page, testInfo, "aumento-pendiente");

  await enviarAumento.click();
  await expect(page.getByText("Sin enviar")).toBeHidden({ timeout: 30_000 });

  // Y en cocina son dos pastillas del mismo pedido, no una con todo mezclado.
  await page.goto("/kds");
  await page.getByRole("link", { name: new RegExp(ESTACION, "i") }).first().click();
  const tarjetas = page.locator("article.kds-card").filter({
    // `#12` no puede casar con `#120`: la cola numera por jornada y sucursal.
    has: page.locator(".kds-orden", { hasText: new RegExp(`^#${numero}(?!\\d)`) }),
  });
  await expect(tarjetas).toHaveCount(2, { timeout: 30_000 });
  await expect(tarjetas.getByText(/aumento 1/)).toBeVisible();
  await capturar(page, testInfo, "kds-dos-tandas");
});

test("el borrador sobrevive a recargar la página", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/pdv");
  await conCajaAbierta(page);

  await page.getByRole("button", { name: "Nuevo pedido" }).click();
  await page.getByRole("button", { name: "Tipo de orden" }).click();
  await dialogo(page).getByRole("button", { name: /Para llevar/ }).click();
  await dialogo(page).getByRole("button", { name: "Confirmar" }).click();
  await marcar(page);
  await capturar(page, testInfo, "borrador-antes-de-recargar");

  // El autoguardado espera a que el cajero deje de teclear.
  await page.waitForTimeout(1_500);
  await page.reload();
  await conCajaAbierta(page);

  // Lo que se perdía: la pestaña volvía en blanco y había que teclear la
  // mesa entera de nuevo.
  await expect(page.getByText(PRODUCTO).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Sin enviar").first()).toBeVisible();
  await capturar(page, testInfo, "borrador-tras-recargar");
});
