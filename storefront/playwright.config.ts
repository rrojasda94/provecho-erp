import { defineConfig, devices } from "@playwright/test";

import { BASE_URL, servidores } from "./playwright.comun";

/**
 * e2e del sitio de marca (ADR-047/ADR-105, PR4): carrito, checkout de
 * invitado, y que la sesión de cuenta sobreviva un refresh — el mismo
 * techo de tres cosas que `frontend/playwright.config.ts` usa para su
 * propia suite ("Qué sí justifica un e2e" en
 * `docs/engineering/testing-strategy.md"), aplicado al sitio público.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results/e2e",
  workers: 1,
  fullyParallel: false,
  // `next dev` compila cada ruta la primera vez que se pide, igual que en
  // la suite del ERP.
  timeout: 180_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: servidores,
});
