import { defineConfig, devices } from "@playwright/test";

import { BASE_URL, servidores } from "./playwright.comun";

/**
 * e2e del flujo del dinero.
 *
 * El techo de esta suite es la lista de tres cosas de
 * `docs/engineering/testing-strategy.md` → "Qué sí justifica un e2e": que la
 * sesión funcione, un flujo del dinero completo, y los candados que solo
 * existen en pantalla. Lo que no entra ahí no se escribe acá — va a `uso/`
 * (ADR-047) o, casi siempre, es un test de contrato o de dominio mal
 * ubicado.
 *
 * Cómo se levantan la API y el frontend está en `playwright.comun.ts`, que
 * comparte con la suite de uso.
 *
 * La API corre contra un SQLite desechable (`e2e.db`) sembrado por
 * `src.seeders.seed` + `src.seeders.e2e`, no contra la base de desarrollo:
 * una prueba que abre y cierra caja deja rastro, y ese rastro no puede caer
 * en los datos con los que alguien está trabajando.
 */
export default defineConfig({
  testDir: "./e2e",
  // Subcarpeta propia y no `test-results/` a secas: Playwright **borra el
  // `outputDir` entero** antes de correr, así que con el defecto esta suite
  // se llevaba puestas las capturas de la de uso cada vez que corría.
  outputDir: "./test-results/e2e",
  // Sin paralelo: las pruebas comparten una sola caja por punto de venta, y
  // dos que abran caja a la vez se pisan. Serializar es más honesto que
  // inventar un punto de venta por worker para un suite de este tamaño.
  workers: 1,
  fullyParallel: false,
  // 30 s (el defecto) no alcanzan: `next dev` compila cada ruta la primera
  // vez que alguien la pide, y este recorrido toca login, home, PDV, la ruta
  // de proxy y sus diálogos. El login solo tarda ~5 s en frío. No es lentitud
  // del código sino del modo desarrollo — se compensa con tiempo en vez de
  // montar un build de producción para el suite.
  //
  // 90 s tampoco alcanzaban **en frío**: con `.next` vacío la corrida moría
  // sobre el cierre de caja, y el síntoma —"esperaba Caja cerrada"— hacía
  // pensar en un bug del cierre. Lo que se agotaba era el presupuesto del
  // test, no el `expect`. El recorrido completo tarda ~96 s en esta máquina;
  // el resto del margen es para el runner de CI, que tiene dos núcleos y
  // siempre compila en frío.
  timeout: 240_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: BASE_URL,
    // Solo del intento que falla: el rastro es para depurar, no para
    // engordar el artefacto de cada corrida verde. La suite de uso hace lo
    // contrario a propósito — ahí la captura *es* el entregable.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: servidores,
});
