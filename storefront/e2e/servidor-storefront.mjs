/**
 * Arranca el Next del sitio de marca apuntando a la API de e2e.
 *
 * Mismo motivo que `frontend/e2e/servidor-web.mjs`: fijar `API_INTERNAL_URL`
 * en el proceso que lo usa, el `env` del `webServer` de Playwright no llega
 * en Windows + npm de intermediario.
 */
import { spawn } from "node:child_process";

process.env.API_INTERNAL_URL ??= `http://127.0.0.1:${process.env.E2E_PUERTO_API ?? "8110"}`;

const PUERTO = process.env.E2E_PUERTO_STOREFRONT ?? "3110";

const hijo = spawn("npm", ["run", "dev", "--", "--port", PUERTO], {
  stdio: "inherit",
  env: process.env,
  shell: process.platform === "win32",
});

hijo.on("exit", (codigo) => process.exit(codigo ?? 0));
