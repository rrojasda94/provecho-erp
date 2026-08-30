import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * El ciclo entero de una compra, por la pantalla.
 *
 * Los cinco endpoints —emitir, recibir, anular, dar conformidad y compra
 * directa— existen y están probados desde que existe el módulo. Lo que no
 * existía era quién los llamara: el listado de OC ofrecía «Editar», y solo en
 * `borrador`. Una orden emitida no tenía ninguna acción en ninguna pantalla,
 * y el turno lo reportó como que la OC era «un ente aislado e inútil».
 *
 * Va en `uso/` y no en `e2e/`: es el flujo del dinero, que es lo que
 * `docs/engineering/testing-strategy.md` da por justificado acá, y el
 * entregable es además la secuencia de capturas.
 *
 * `serial`: los dos recorridos comparten el proveedor sembrado, y la factura
 * de proveedor es única por (emisor, serie, número). Corriendo en paralelo se
 * pisarían el número.
 */

test.describe.configure({ mode: "serial" });

const PROVEEDOR = "Distribuidora E2E SAC";

test("una OC en borrador se emite, se recibe y se factura", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/compras/ordenes-compra");
  await capturar(page, testInfo, "ordenes-de-compra");

  // El seeder deja la OC en borrador a propósito: emitirla es un paso que
  // esta prueba tiene que dar por la pantalla, con su candado de umbral.
  await page.getByRole("link", { name: PROVEEDOR }).first().click();
  // Se espera la navegación antes de mirar el contenido: el listado tiene sus
  // dos diálogos siempre en el DOM y «borrador» aparece en tres lugares ahí.
  await expect(page).toHaveURL(/\/compras\/ordenes-compra\/[0-9a-f-]{36}/);
  await expect(page.getByTestId("estado-oc")).toContainText("borrador");
  await capturar(page, testInfo, "ficha-en-borrador");

  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Emitir" }).click();
  await expect(page.getByTestId("estado-oc")).toContainText("emitida");

  await page.getByRole("button", { name: "Registrar recepción" }).click();
  await expect(dialogo(page)).toBeVisible();
  await capturar(page, testInfo, "recepcion");
  // Las cantidades vienen precargadas con lo que falta: teclear de nuevo lo
  // que el sistema ya sabe es donde se equivoca quien está apurado.
  await dialogo(page).getByRole("button", { name: "Registrar" }).click();
  await expect(page.getByTestId("estado-oc")).toContainText("recibida");

  await page.getByRole("button", { name: "Registrar factura" }).click();
  await expect(dialogo(page)).toBeVisible();
  await dialogo(page).getByLabel("Serie").fill("F900");
  await dialogo(page).getByLabel("Número").fill("1");
  await dialogo(page).getByLabel("Total del documento").fill("500.00");
  await capturar(page, testInfo, "factura-del-proveedor");
  await dialogo(page).getByRole("button", { name: "Dar conformidad" }).click();

  await expect(page.getByText("F900-1")).toBeVisible();
  await capturar(page, testInfo, "oc-facturada");

  // Y aparece en el registro de compras, que antes no existía: una factura
  // registrada solo se volvía a ver entrando a la OC, si uno recordaba cuál.
  await page.goto("/compras/facturas");
  await expect(page.getByText("F900-1")).toBeVisible();
  await capturar(page, testInfo, "registro-de-compras");
});

test("una compra directa se registra con su factura en un paso", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/compras/directas");
  await capturar(page, testInfo, "compra-directa");

  await page.getByRole("combobox", { name: "Proveedor" }).click();
  await page.getByRole("option", { name: PROVEEDOR }).first().click();
  await page.getByRole("combobox", { name: "Almacén destino" }).click();
  await page.getByRole("option").first().click();

  await page.getByRole("combobox", { name: "Artículo" }).first().click();
  await page.getByRole("option").first().click();
  await page.getByPlaceholder("Cant.").fill("3");
  await page.getByPlaceholder("Costo").fill("12.50");

  await page.getByLabel("Serie").fill("B900");
  await page.getByLabel("Número").fill("77");
  await page.getByLabel("Total del documento").fill("44.25");
  await capturar(page, testInfo, "compra-directa-llena");

  await page.getByRole("button", { name: "Registrar la compra" }).click();

  // Termina en la ficha de la OC que creó: el resultado es una orden ya
  // recibida y conforme, y esa ficha es el único lugar donde vive.
  await expect(page).toHaveURL(/\/compras\/ordenes-compra\/[0-9a-f-]{36}/);
  await expect(page.getByTestId("origen-oc")).toContainText("Compra directa");
  await expect(page.getByText("B900-77")).toBeVisible();
  await capturar(page, testInfo, "compra-directa-registrada");
});
