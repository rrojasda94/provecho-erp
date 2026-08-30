import { expect, test } from "@playwright/test";

import { ADMIN, contar, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * La vuelta al PDV desde la cola de despacho.
 *
 * El despacho se abre **dentro** del PDV como overlay (ADR-078): salir del
 * PDV cerraría la caja de la vista y descartaría el pedido a medio armar.
 * Pero lo único que ofrecía para volver era una `×` sin etiqueta, flotando
 * encima del encabezado del KDS. El turno la reportó como "no tiene el botón
 * de regresar al PDV" — que es exactamente lo que pasaba: el botón estaba,
 * pero no decía a dónde llevaba, así que no era el botón que buscaban.
 *
 * Va en `uso/` y no en `e2e/`: el techo de la suite obligatoria son tres
 * cosas y ninguna es esta (`docs/engineering/testing-strategy.md`). Lo que
 * se afirma acá es que la salida **se puede nombrar**, y eso solo se ve
 * buscándola por su rótulo.
 */

/** El PDV no muestra la carta sin caja abierta (ADR-025), y la caja es del
 * punto de venta: puede venir abierta de otro recorrido de esta misma suite.
 * Mismo patrón que `pdv-aumento-y-borrador.spec.ts`. */
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

test("el despacho abierto desde el PDV se cierra con un botón que dice a dónde vuelve", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/pdv");
  await conCajaAbierta(page);
  await capturar(page, testInfo, "pdv");

  await page.getByRole("button", { name: "Ver la cola de despacho" }).click();
  await expect(dialogo(page)).toBeVisible();

  // El rótulo es lo que se prueba. Un `aria-label` en una `×` pasaba esta
  // afirmación y no resolvía el reporte: lo que faltaba era texto visible.
  const volver = dialogo(page).getByRole("button", { name: "Volver al PDV" });
  await expect(volver).toBeVisible();
  await capturar(page, testInfo, "despacho-en-pdv");

  await volver.click();
  await expect(dialogo(page)).toBeHidden();
  // Y la caja sigue abierta detrás: volver no es navegar, es cerrar el
  // overlay — que es el motivo por el que el despacho se embebe.
  await expect(page.getByTestId("estado-caja")).toContainText("Caja abierta");
  await capturar(page, testInfo, "de-vuelta-en-el-pdv");
});
