import { defineConfig, devices } from "@playwright/test";

import { BASE_URL, servidores } from "./playwright.comun";

/**
 * Pruebas de uso: recorridos completos, con captura en cada hito (ADR-047).
 *
 * No es "más e2e". La suite de `e2e/` responde *¿arranca y se hablan?* y por
 * eso tiene un techo de tres casos: cada uno cuesta minutos y bloquea todo
 * merge. Ésta responde otra pregunta —*¿esto se puede usar de punta a
 * punta?*— y su salida no es el verde: son las capturas, que es lo que
 * permite mirar una pantalla sin instalar el ERP.
 *
 * Por eso las tres diferencias con la config de e2e, y son las tres a
 * propósito:
 *
 * - `screenshot: "on"` y `trace: "on"`, no `on-failure`. Una corrida verde
 *   sin capturas no entrega nada.
 * - `retries: 0`. Un reintento tapa una pantalla intermitente, que acá es
 *   justo el hallazgo que se busca.
 * - **No es un check requerido** (`.github/workflows/ci.yml`, job `uso`): un
 *   recorrido lento no puede bloquear un arreglo de caja.
 *
 * Cómo se levantan la API y el frontend está en `playwright.comun.ts`: es
 * exactamente el mismo arranque que el de e2e, contra el mismo SQLite
 * desechable y el mismo seeder.
 */
export default defineConfig({
  testDir: "./uso",
  // Separado del de e2e porque Playwright **borra el `outputDir` entero**
  // antes de correr: compartirlo hace que la última suite que corra sea la
  // única que deja capturas.
  outputDir: "./test-results/uso",
  // Mismo motivo que en e2e: se comparte una sola caja por punto de venta.
  workers: 1,
  fullyParallel: false,
  // Un recorrido de uso toca más pantallas que un e2e, y `next dev` compila
  // cada ruta la primera vez que se la pide.
  timeout: 300_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on",
    screenshot: "on",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: servidores,
});
