/**
 * Arranca la API de las pruebas e2e contra su SQLite desechable.
 *
 * Mismo motivo que `servidor-web.mjs`: el `env` del `webServer` de
 * Playwright no llega al proceso hijo en este entorno, y sin
 * `DATABASE_URL` la API toma la del `.env` del repo — **la base de
 * desarrollo en Supabase**. Una suite que abre y cierra caja escribiendo en
 * la base con la que alguien está trabajando es peor que una suite que no
 * corre, y encima el fallo no se nota: los tests pasan.
 *
 * Fijar la variable dentro del proceso que la usa quita el intermediario.
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const hijo = spawn(
  process.env.PYTHON ?? "python",
  ["-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8100"],
  {
    cwd: RAIZ,
    stdio: "inherit",
    env: {
      ...process.env,
      DATABASE_URL: "sqlite:///./e2e.db",
      ENVIRONMENT: "local",
      // Sin token no se encola nada a Factiliza: la prueba cobra de verdad
      // pero no le habla a SUNAT.
      FACTILIZA_TOKEN: "",
    },
  },
);

hijo.on("exit", (codigo) => process.exit(codigo ?? 0));
