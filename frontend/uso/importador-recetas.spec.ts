import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { escribirPlanilla, leerPlanilla } from "./planilla";
import { capturar } from "./util";

/**
 * Carga masiva del recetario, de punta a punta (ADR-046).
 *
 * Existe por un agujero, no por completitud. La plantilla se descargaba
 * como un JSON ilegible y la subida ni siquiera llegaba al servidor: el
 * proxy del navegador decodificaba los cuerpos a texto y les fijaba
 * `application/json` en las dos direcciones (ADR-048). El backend estaba
 * bien —`tests/test_recetas_variantes.py` lo probaba y pasaba— porque
 * ataca a FastAPI con `TestClient`, sin pasar por el proxy. Nada recorría
 * el camino que recorre una persona, y por eso nada lo vio.
 *
 * Lo que este recorrido afirma que un test de unidad no puede:
 *
 * - El archivo que **el navegador guarda** empieza con `PK\\x03\\x04` (todo
 *   `.xlsx` es un ZIP), se llama `.xlsx`, y **openpyxl lo abre** — la misma
 *   librería que va a leerlo cuando alguien lo suba lleno.
 * - Ese archivo se sube por `multipart` con su `boundary` intacto, la
 *   revisión de la fase 1 lo entiende, y lo confirmado aparece en el
 *   listado.
 *
 * Los datos que la planilla nombra son los que siembra `src/seeders/e2e.py`
 * —la unidad «Kilo», el insumo «Harina E2E»— más uno inventado a propósito,
 * que es el que obliga a pasar por la resolución de insumos desconocidos.
 */

const RECETA = "Salsa Uso";
/** El insumo que el catálogo no conoce. Sin él la revisión no tendría nada
 * que resolver y el recorrido saltearía la mitad de la pantalla. */
const DESCONOCIDO = "Tomate Inexistente";
/** Un artículo sembrado, distinto de «Harina E2E»: un mismo insumo dos veces
 * en la misma receta es `Conflicto` y la receta entera se omitiría. */
const RESUELTO_A = "Queso E2E";

/** Los cuatro bytes con los que empieza cualquier ZIP, y por lo tanto
 * cualquier `.xlsx`. Es lo primero que se pierde al decodificar a texto. */
const FIRMA_ZIP = Buffer.from([0x50, 0x4b, 0x03, 0x04]);

test("el recetario se descarga, se llena y se carga de golpe", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /^Catálogo/ }).click();
  await page.getByRole("link", { name: "Recetas", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recetas", exact: true })).toBeVisible();
  await capturar(page, testInfo, "recetas");

  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await expect(dialogo(page).getByText("Importar recetario")).toBeVisible();
  await capturar(page, testInfo, "dialogo-importar");

  // --- La bajada ------------------------------------------------------------
  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    dialogo(page).getByRole("link", { name: /Descargar plantilla/ }).click(),
  ]);

  // El `<a download>` va **sin valor**, así que el nombre lo decide el
  // navegador: usa el `filename` del `Content-Disposition` si llega, y si no
  // el último segmento de la URL — que es «plantilla», sin extensión.
  expect(descarga.suggestedFilename()).toBe("plantilla-recetas.xlsx");

  const bajada = testInfo.outputPath("plantilla-recetas.xlsx");
  await descarga.saveAs(bajada);
  const bytes = readFileSync(bajada);

  expect(bytes.subarray(0, 4)).toEqual(FIRMA_ZIP);
  // Que abra con openpyxl es la afirmación que importa: un ZIP truncado o
  // con un byte cambiado también empieza con `PK`.
  const plantilla = await leerPlanilla(bajada);
  expect(plantilla.hojas).toEqual(["Recetas", "Ingredientes", "Instrucciones"]);
  expect(plantilla.primeraFila).toEqual([
    // La columna `ID` va primera y vacía en la plantilla: llena significa
    // «actualiza esta receta» (ADR-052).
    "ID",
    "Receta",
    "Rendimiento",
    "Unidad",
    "Produce el artículo",
  ]);

  // --- La subida ------------------------------------------------------------
  const llenada = testInfo.outputPath("recetario-lleno.xlsx");
  await escribirPlanilla(llenada, {
    Recetas: [
      ["ID", "Receta", "Rendimiento", "Unidad", "Produce el artículo"],
      ["", RECETA, 2, "Kilo", ""],
    ],
    Ingredientes: [
      ["Receta", "Insumo", "Cantidad", "Merma %"],
      // «450/3» es aritmética tecleada (RN-COM-024): la hoja acepta lo mismo
      // que la pantalla, y el redondeo lo hace el servidor.
      [RECETA, "Harina E2E", "450/3", 5],
      [RECETA, DESCONOCIDO, 1, 0],
    ],
  });

  await dialogo(page).locator('input[type="file"]').setInputFiles(llenada);

  await expect(dialogo(page).getByText(/nueva\(s\)/)).toBeVisible();
  await expect(dialogo(page).getByText(DESCONOCIDO)).toBeVisible();
  await capturar(page, testInfo, "revision");

  await dialogo(page).locator("select").selectOption({ label: RESUELTO_A });
  await dialogo(page).getByRole("button", { name: /^Importar \d+ fila/ }).click();

  await expect(dialogo(page).getByText(/1 importada\(s\)/)).toBeVisible();
  await capturar(page, testInfo, "importada");

  // --- El listado -----------------------------------------------------------
  await dialogo(page).getByRole("button", { name: "Cerrar" }).click();
  // La tabla pagina de a 10 y el seeder deja bastantes más recetas: sin
  // buscar, la recién creada puede estar en otra página y la prueba fallaría
  // por la paginación, no por la importación.
  await page.getByLabel("Buscar receta...").fill(RECETA);
  await expect(page.getByRole("link", { name: RECETA, exact: true })).toBeVisible();
  await capturar(page, testInfo, "listado");
});
