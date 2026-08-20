import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { escribirPlanilla, leerPlanilla } from "./planilla";
import { capturar } from "./util";

/**
 * Carga masiva del catálogo de artículos, de punta a punta (ADR-051).
 *
 * Calcado del recorrido de recetas, y por el mismo motivo: lo que un test de
 * unidad no puede afirmar es que el archivo que **el navegador guarda** sea
 * un `.xlsx` de verdad, que openpyxl lo abra, y que la subida llegue con su
 * `boundary` intacto al otro lado del proxy (ADR-048).
 *
 * Lo propio de esta entidad es el round-trip: se baja el catálogo **con los
 * datos adentro**, se le cambia el nombre a un artículo sembrado, y se sube
 * de vuelta. Que la revisión diga «a actualizar» y no «nuevo» es lo que
 * prueba que la columna `ID` viajó y volvió intacta.
 */

const CODIGO_NUEVO = "UZ01";
const NOMBRE_NUEVO = "Aceite Uso";
/** Un artículo que siembra `src/seeders/e2e.py`. */
const SEMBRADO = "Queso E2E";

const FIRMA_ZIP = Buffer.from([0x50, 0x4b, 0x03, 0x04]);

test("el catálogo se descarga, se llena y se carga de golpe", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /^Inventario/ }).click();
  await page.getByRole("link", { name: "Artículos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Artículos", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await expect(dialogo(page).getByText("Importar artículos")).toBeVisible();
  await capturar(page, testInfo, "dialogo-importar");

  // --- La bajada: el catálogo con los datos adentro -------------------------
  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    dialogo(page).getByRole("link", { name: /Descargar lo que ya está cargado/ }).click(),
  ]);
  expect(descarga.suggestedFilename()).toBe("articulos.xlsx");

  const bajada = testInfo.outputPath("articulos.xlsx");
  await descarga.saveAs(bajada);
  expect(readFileSync(bajada).subarray(0, 4)).toEqual(FIRMA_ZIP);

  const exportado = await leerPlanilla(bajada);
  expect(exportado.hojas).toEqual(["Artículos", "SKUs", "Instrucciones"]);
  expect(exportado.primeraFila[0]).toBe("ID");
  expect(exportado.primeraFila[1]).toBe("Código");

  // --- La subida: un alta nueva ---------------------------------------------
  const llenada = testInfo.outputPath("catalogo-lleno.xlsx");
  await escribirPlanilla(llenada, {
    Artículos: [
      [
        "ID", "Código", "Nombre", "Tipo", "Unidad", "Categoría",
        "Costo promedio", "Controla lote", "Días alerta vencimiento", "Archivado",
      ],
      ["", CODIGO_NUEVO, NOMBRE_NUEVO, "insumo", "Kilo", "", "12.5", "No", "", "No"],
    ],
    SKUs: [["Artículo", "Código", "Código de barras", "Activo"]],
  });

  await dialogo(page).locator('input[type="file"]').setInputFiles(llenada);
  await expect(dialogo(page).getByText(/nuevo\(s\)/)).toBeVisible();
  await capturar(page, testInfo, "revision");

  await dialogo(page).getByRole("button", { name: /^Importar \d+ fila/ }).click();
  await expect(dialogo(page).getByText(/1 importada\(s\)/)).toBeVisible();
  await capturar(page, testInfo, "importado");

  await dialogo(page).getByRole("button", { name: "Cerrar" }).click();
  await page.getByLabel("Buscar artículo...").fill(NOMBRE_NUEVO);
  await expect(page.getByText(NOMBRE_NUEVO, { exact: true })).toBeVisible();
  await capturar(page, testInfo, "listado");
});

test("un artículo que ya existe se actualiza, no se duplica", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /^Inventario/ }).click();
  await page.getByRole("link", { name: "Artículos", exact: true }).click();
  await page.getByRole("button", { name: "Importar", exact: true }).click();

  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    dialogo(page).getByRole("link", { name: /Descargar lo que ya está cargado/ }).click(),
  ]);
  const bajada = testInfo.outputPath("catalogo-actual.xlsx");
  await descarga.saveAs(bajada);

  // Se sube el mismo archivo sin tocar: todo tiene que salir «a actualizar»,
  // que es la prueba de que el export y el importador hablan el mismo idioma.
  await dialogo(page).locator('input[type="file"]').setInputFiles(bajada);
  // El contador, no el encabezado de la seccion: los dos dicen "a actualizar"
  // y un locator ambiguo falla por strict mode sin probar nada.
  await expect(dialogo(page).getByText(/nuevo\(s\).+a actualizar/)).toBeVisible();
  await expect(dialogo(page).getByText(SEMBRADO, { exact: false }).first()).toBeVisible();
  await capturar(page, testInfo, "round-trip");
});
