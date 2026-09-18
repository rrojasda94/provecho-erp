/**
 * Arranca la API de las pruebas e2e del sitio contra su SQLite desechable.
 *
 * Mismo motivo que `frontend/e2e/servidor-api.mjs`: fijar `DATABASE_URL`
 * en el proceso que la usa, no en el `env` del `webServer` de Playwright
 * (no llega en Windows + npm de intermediario).
 *
 * `STOREFRONT_MARCA_ID` se resuelve acá, no se hardcodea: `preparar-bd.mjs`
 * ya sembró la marca "Charlie's Pizzas" con un id nuevo cada corrida (UUID
 * aleatorio), y `Settings` lo lee una sola vez al arrancar — tiene que
 * estar en el `env` de este proceso antes del primer `import`.
 */
import { execFileSync, spawn } from "node:child_process";

import { RAIZ, interprete } from "./interprete.mjs";

const PUERTO = process.env.E2E_PUERTO_API ?? "8110";

const RESOLVER_MARCA = `
import src.core.models_registry  # noqa: F401
from sqlalchemy import select
from src.core.database import engine
from sqlalchemy.orm import Session
from src.modules.users.infrastructure.models import Marca
with Session(engine) as s:
    marca = s.scalar(select(Marca).where(Marca.nombre == "Charlie's Pizzas"))
    print(marca.id if marca else "")
`;

const marcaId = execFileSync(
  interprete(),
  ["-c", RESOLVER_MARCA],
  {
    cwd: RAIZ,
    encoding: "utf8",
    env: { ...process.env, DATABASE_URL: "sqlite:///./storefront/e2e.db" },
  },
).trim();

if (!marcaId) {
  console.error("No se encontró la marca 'Charlie's Pizzas' — corré preparar-bd.mjs primero.");
  process.exit(1);
}

const hijo = spawn(
  interprete(),
  ["-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", PUERTO],
  {
    cwd: RAIZ,
    stdio: "inherit",
    env: {
      ...process.env,
      DATABASE_URL: "sqlite:///./storefront/e2e.db",
      ENVIRONMENT: "local",
      FACTILIZA_TOKEN: "",
      STOREFRONT_MARCA_ID: marcaId,
      STOREFRONT_CANAL: "web",
      STOREFRONT_MODALIDAD: "delivery",
    },
  },
);

hijo.on("exit", (codigo) => process.exit(codigo ?? 0));
