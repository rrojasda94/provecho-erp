import { expect, test } from "@playwright/test";

import { ADMIN, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Humo del arnés de uso: entrar y llegar al home, capturando cada hito.
 *
 * No prueba nada que `e2e/sesion.spec.ts` no pruebe mejor y más barato — y
 * eso es a propósito. Lo que verifica es **el arnés**: que
 * `playwright.uso.config.ts` levante los mismos dos servidores, que la BD
 * sembrada esté ahí, y que la corrida deje capturas en `test-results/uso/`
 * incluso cuando pasa. Sin un caso, esas tres cosas se descubren rotas
 * recién cuando la primera rama intenta escribir un recorrido de verdad.
 *
 * Los recorridos reales —vender una pizza con variantes y extras, recibir
 * una orden de compra— los escriben otras ramas sobre este arnés y sobre lo
 * que ya siembra `src/seeders/e2e.py`.
 */

test("el admin entra y llega al home", async ({ page }, testInfo) => {
  await page.goto("/login");
  await capturar(page, testInfo, "login");

  await ingresar(page, ADMIN);
  // `ingresar` ya afirma el saludo; acá se mira que el home traiga sus
  // módulos, que es lo que hace de esta pantalla un punto de partida y no
  // una confirmación de login.
  //
  // Anclado con `^`: el nombre accesible de cada ficha es su título **más su
  // bajada**, y la de Dashboard dice "Ventas del día, stock bajo mínimo…".
  // Un `/Ventas/i` suelto encuentra dos fichas y Playwright lo rechaza por
  // modo estricto. En `e2e/sesion.spec.ts` el mismo locator funciona porque
  // ahí entra el cajero, que no ve Dashboard — y esa diferencia es
  // exactamente la clase de trampa que un recorrido de admin destapa.
  await expect(page.getByRole("link", { name: /^Ventas/ })).toBeVisible();
  await capturar(page, testInfo, "home");
});
