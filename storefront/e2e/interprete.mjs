/**
 * De dónde sale el Python que corre la API de las pruebas.
 *
 * `process.env.PYTHON ?? "python"` alcanzaba mientras el repo se trabajaba
 * desde un solo checkout. Con varias sesiones en paralelo ya no: cada rama
 * vive en su propio worktree (`.claude/worktrees/<rama>`) y **ninguno tiene
 * `.venv` propio** — el entorno virtual se instaló una vez en la raíz del
 * repo principal y ahí se quedó. El `python` del PATH, cuando existe, es el
 * del sistema: sin `fastapi`, sin `sqlalchemy`, sin el paquete `src`
 * instalado en modo editable. El síntoma no dice nada de entornos virtuales,
 * dice `ModuleNotFoundError: No module named 'src'`, y aparece en el paso de
 * preparar la base, tres pasos antes de la prueba que alguien quería correr.
 *
 * La cadena de resolución va de lo más específico a lo más general:
 *
 *   1. `PYTHON`, si quien corre la suite lo fijó. Sigue mandando sobre todo
 *      lo demás: es el escape para un entorno que no está donde se busca.
 *   2. El `.venv` del propio worktree, si alguien se lo creó.
 *   3. El `.venv` de la raíz del repo principal, que es el caso real de todo
 *      worktree. Se llega por `git rev-parse --git-common-dir`, que apunta al
 *      `.git` compartido, en vez de contar cuántos `..` hay hasta salir de
 *      `.claude/worktrees/<x>` — esa cuenta se rompe el día que la carpeta
 *      cambie de profundidad.
 *   4. `python` a secas. Es lo que había antes: si el repo se usa desde un
 *      checkout normal con el entorno activado, sigue funcionando igual.
 *
 * Nada de esto se puede resolver commiteando una ruta: la del `.venv` es
 * absoluta y distinta en cada máquina.
 */
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Raíz del checkout desde el que se corre (worktree o repo principal). */
export const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const EJECUTABLE = process.platform === "win32"
  ? path.join(".venv", "Scripts", "python.exe")
  : path.join(".venv", "bin", "python");

function venvDe(raiz) {
  const candidato = path.join(raiz, EJECUTABLE);
  return existsSync(candidato) ? candidato : null;
}

/** Raíz del repo principal, o `null` si no se puede averiguar. */
function raizPrincipal() {
  try {
    // `git` es un `.exe` en Windows, así que no necesita `shell: true` (que
    // además metería el intérprete de comandos en el medio sin motivo).
    const gitComun = execFileSync(
      "git",
      ["rev-parse", "--path-format=absolute", "--git-common-dir"],
      { cwd: RAIZ, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
    // `.../<repo>/.git` → `.../<repo>`
    return gitComun ? path.dirname(gitComun) : null;
  } catch {
    return null;
  }
}

export function interprete() {
  if (process.env.PYTHON) return process.env.PYTHON;

  const propio = venvDe(RAIZ);
  if (propio) return propio;

  const principal = raizPrincipal();
  if (principal && principal !== RAIZ) {
    const compartido = venvDe(principal);
    if (compartido) return compartido;
  }

  return "python";
}
