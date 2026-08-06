/**
 * Rehace la base de e2e desde cero. Corre **antes** de `playwright test`,
 * no como `globalSetup`.
 *
 * El orden importa y no es el intuitivo: Playwright levanta los `webServer`
 * **antes** de ejecutar `globalSetup`, así que la API ya tiene el archivo
 * SQLite abierto cuando el setup intentaría borrarlo — en Windows eso falla
 * con un `EPERM` que no menciona la palabra "servidor" por ningún lado.
 * Preparar la base en un paso previo del script de npm quita el problema en
 * vez de esquivarlo.
 *
 * Por qué rehacer y no reusar: los seeders son idempotentes, pero el
 * **estado de la caja** no. Una corrida que deja un turno abierto hace
 * fallar a la siguiente en el primer `expect` de la apertura, y el mensaje
 * dice "no aparece el diálogo", no "la corrida anterior no limpió".
 */
import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, "..", "..");
const PYTHON = process.env.PYTHON ?? "python";

const PREPARAR = `
import src.core.models_registry  # noqa: F401
from src.core.database import Base, SessionLocal, engine
from src.seeders.e2e import sembrar_e2e
from src.seeders.seed import seed

Base.metadata.create_all(engine)
with SessionLocal() as s:
    seed(s)
    datos = sembrar_e2e(s)
    s.commit()
print("base e2e lista:", datos)
`;

try {
  rmSync(path.join(RAIZ, "e2e.db"), { force: true });
} catch (e) {
  throw new Error(
    "No se pudo borrar e2e.db: quedó un proceso sosteniendo el archivo " +
      "(normalmente una API de una corrida interrumpida). Cerralo y volvé a " +
      `correr. (${e.message})`,
  );
}

execFileSync(PYTHON, ["-c", PREPARAR], {
  cwd: RAIZ,
  env: { ...process.env, DATABASE_URL: "sqlite:///./e2e.db", ENVIRONMENT: "local" },
  stdio: "inherit",
});
