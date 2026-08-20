import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { escribirPlanilla, leerPlanilla } from "./planilla";
import { capturar } from "./util";

/**
 * Carga masiva del padrón de clientes, de punta a punta (RN-PTS-007).
 *
 * Mismo motivo que los otros dos recorridos: que el archivo que el navegador
 * guarda sea un `.xlsx` de verdad y que la subida llegue entera al otro lado
 * del proxy (ADR-048).
 *
 * Lo propio de esta entidad es que el tipo **no se declara**: once dígitos son
 * un RUC y hacen al cliente jurídico (RN-PTS-002). Por eso la planilla sube
 * un natural con teléfono y el listado tiene que mostrarlo como natural.
 */

const NOMBRE = "Cliente Uso";
const TELEFONO = "955444333";
/** El cliente jurídico que siembra `src/seeders/e2e.py`, con la razón social
 * tecleada mal a propósito. */
const CLIENTE_SEMBRADO = "razon social tecleada a mano";

const FIRMA_ZIP = Buffer.from([0x50, 0x4b, 0x03, 0x04]);

test("el padrón se descarga, se llena y se carga de golpe", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /^Ventas/ }).click();
  await page.getByRole("link", { name: "Clientes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Clientes", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await expect(dialogo(page).getByText("Importar clientes")).toBeVisible();
  await capturar(page, testInfo, "dialogo-importar");

  // --- La bajada: el padrón con los datos adentro ---------------------------
  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    dialogo(page).getByRole("link", { name: /Descargar lo que ya está cargado/ }).click(),
  ]);
  expect(descarga.suggestedFilename()).toBe("clientes.xlsx");

  const bajada = testInfo.outputPath("clientes.xlsx");
  await descarga.saveAs(bajada);
  expect(readFileSync(bajada).subarray(0, 4)).toEqual(FIRMA_ZIP);

  const exportado = await leerPlanilla(bajada);
  expect(exportado.hojas).toEqual(["Clientes", "Instrucciones"]);
  expect(exportado.primeraFila[0]).toBe("ID");
  expect(exportado.primeraFila[2]).toBe("Nombre / Razón social");

  // --- La subida ------------------------------------------------------------
  const llenada = testInfo.outputPath("padron-lleno.xlsx");
  await escribirPlanilla(llenada, {
    Clientes: [
      [
        "ID", "Tipo", "Nombre / Razón social", "Tipo de documento",
        "Número de documento", "Teléfono", "Email", "Dirección / contacto",
        "Fecha de nacimiento",
      ],
      // Sin documento a propósito: el teléfono alcanza para registrarlo
      // (RN-PTS-002) y es el caso real del mostrador.
      ["", "", NOMBRE, "dni", "", TELEFONO, "", "Jr. Uso 100", ""],
    ],
  });

  await dialogo(page).locator('input[type="file"]').setInputFiles(llenada);
  await expect(dialogo(page).getByText(/nuevo\(s\)/)).toBeVisible();
  await capturar(page, testInfo, "revision");

  await dialogo(page).getByRole("button", { name: /^Importar \d+ fila/ }).click();
  await expect(dialogo(page).getByText(/1 importada\(s\)/)).toBeVisible();
  await capturar(page, testInfo, "importado");

  await dialogo(page).getByRole("button", { name: "Cerrar" }).click();
  await page.getByLabel("Buscar por nombre, documento o teléfono...").fill(NOMBRE);
  await expect(page.getByText(NOMBRE, { exact: true })).toBeVisible();
  await capturar(page, testInfo, "listado");
});

test("el padrón exportado se vuelve a subir sin duplicar a nadie", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /^Ventas/ }).click();
  await page.getByRole("link", { name: "Clientes", exact: true }).click();
  await page.getByRole("button", { name: "Importar", exact: true }).click();

  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    dialogo(page).getByRole("link", { name: /Descargar lo que ya está cargado/ }).click(),
  ]);
  const bajada = testInfo.outputPath("padron-actual.xlsx");
  await descarga.saveAs(bajada);

  // El round-trip nulo: el mismo archivo, sin tocar. Todo «a actualizar» y
  // nada nuevo — es la prueba de que el export y el importador hablan el
  // mismo idioma, y de que la columna `ID` viajó y volvió intacta.
  await dialogo(page).locator('input[type="file"]').setInputFiles(bajada);
  // El contador, no el encabezado de la seccion: los dos dicen "a actualizar"
  // y un locator ambiguo falla por strict mode sin probar nada. Que empiece en
  // "0 nuevo(s)" es la mitad que importa: el round-trip no crea a nadie.
  await expect(dialogo(page).getByText(/^0 nuevo\(s\).+a actualizar/)).toBeVisible();
  // El cliente sembrado se reconoce por su RUC, no por su razón social —
  // que es justamente lo que se edita (ADR-051).
  await expect(dialogo(page).getByText(CLIENTE_SEMBRADO)).toBeVisible();
  await capturar(page, testInfo, "round-trip");
});
