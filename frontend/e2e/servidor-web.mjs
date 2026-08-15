/**
 * Arranca el Next de las pruebas e2e apuntando a la API de e2e.
 *
 * Existe porque el `env` del `webServer` de Playwright **no llega** al
 * proceso de Next en este entorno (Windows + npm como intermediario): el
 * servidor arranca bien, sirve las páginas, y recién falla cuando una
 * Server Action intenta hablar con la API — se va al `http://localhost:8000`
 * por defecto, donde no hay nadie, y en Windows esa conexión no rebota:
 * **se cuelga**. El síntoma es un botón en "Ingresando..." para siempre y
 * ningún error en ningún log.
 *
 * Fijar la variable dentro del proceso que la usa quita el intermediario y
 * con él toda la clase de problema.
 */
import { spawn } from "node:child_process";

process.env.API_INTERNAL_URL ??= `http://127.0.0.1:${process.env.E2E_PUERTO_API ?? "8100"}`;

// 3100 salvo que otro agente ya lo tenga tomado. Con el puerto web fijo en
// el código, dos worktrees no podían correr Playwright a la vez: el segundo
// arrancaba su Next contra un 3100 ocupado —o peor, reusaba el del primero,
// que apunta a **otra** API— y fallaba con errores que no mencionan puertos.
// El esquema de slots está en `docs/engineering/trabajo-en-paralelo.md`.
const PUERTO = process.env.E2E_PUERTO_WEB ?? "3100";

// `shell: true` en Windows: sin eso, spawn de un `.cmd` falla con EINVAL
// desde Node 20 (endurecimiento contra inyección de comandos). Los
// argumentos son literales del repo, no entrada de nadie.
const hijo = spawn("npm", ["run", "dev", "--", "--port", PUERTO], {
  stdio: "inherit",
  env: process.env,
  shell: process.platform === "win32",
});

hijo.on("exit", (codigo) => process.exit(codigo ?? 0));
