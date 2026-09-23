import type { PlaywrightTestConfig } from "@playwright/test";

/**
 * Cómo se levanta el sitio para sus pruebas e2e (ADR-047, mismo criterio
 * que `frontend/playwright.comun.ts`): dos servidores, la API contra un
 * SQLite desechable propio de esta suite (`storefront/e2e.db`, no
 * `frontend/e2e.db` — son bases independientes, cada una con su propio
 * `preparar-bd.mjs`) y el sitio en modo desarrollo.
 *
 * Puertos en el rango 811N/311N y no 810N/310N: para no chocar con la
 * suite del ERP si algún día corren en la misma máquina a la vez (el
 * esquema de slots por agente sigue siendo
 * `docs/engineering/trabajo-en-paralelo.md`, esto es un slot fijo más).
 */
export const PUERTO_API = process.env.E2E_PUERTO_API ?? "8110";
export const PUERTO_STOREFRONT = process.env.E2E_PUERTO_STOREFRONT ?? "3110";
export const BASE_URL = `http://localhost:${PUERTO_STOREFRONT}`;

const REUSAR = !!process.env.E2E_REUSAR;

export const servidores: PlaywrightTestConfig["webServer"] = [
  {
    command: "node e2e/servidor-api.mjs",
    url: `http://127.0.0.1:${PUERTO_API}/health`,
    reuseExistingServer: REUSAR,
    timeout: 120_000,
  },
  {
    command: "node e2e/servidor-storefront.mjs",
    url: `${BASE_URL}/carta`,
    reuseExistingServer: REUSAR,
    timeout: 180_000,
  },
];
