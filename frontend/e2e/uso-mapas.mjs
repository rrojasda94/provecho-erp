/**
 * Arranca el recorrido del campo de dirección **con** mapa (`uso/
 * direccion-con-mapa.spec.ts`), que necesita un Next con
 * `GOOGLE_MAPS_BROWSER_KEY` puesta.
 *
 * Va en su propio arranque y no junto al resto de `uso/` por una razón
 * concreta: ponerle la clave al servidor compartido haría que **toda**
 * pantalla con un campo de dirección saliera a pedirle el SDK a Google de
 * verdad, con una clave inválida, en cada corrida de CI. Eso es una llamada a
 * un tercero desde el CI y una suite que se pone roja cuando Google anda mal.
 * Acá la clave es de mentira y el SDK lo responde Playwright interceptando la
 * carga; nadie sale a la red.
 *
 * Misma razón que `servidor-web.mjs` para fijar la variable en el proceso que
 * la usa en vez de pasarla por `env:` de Playwright: en Windows, con npm de
 * intermediario, no llega.
 */
import { spawn } from "node:child_process";

// De mentira a propósito: el SDK nunca sale a Google, lo devuelve la ruta
// interceptada. Lo único que importa es que NO esté vacía, porque el campo
// solo intenta cargar el mapa cuando hay clave.
process.env.GOOGLE_MAPS_BROWSER_KEY ??= "clave-de-mentira-para-pruebas";

// `--output` propio: Playwright **borra el directorio de salida entero**
// antes de correr, así que compartirlo con `test:uso` haría que el último en
// correr fuera el único que deja capturas.
const hijo = spawn(
  "npx",
  [
    "playwright",
    "test",
    "--config",
    "playwright.uso.config.ts",
    "--output",
    "test-results/uso-mapas",
    "uso/direccion-con-mapa.spec.ts",
  ],
  {
    stdio: "inherit",
    env: process.env,
    // `shell: true` en Windows: sin eso, spawn de un `.cmd` falla con EINVAL
    // desde Node 20. Los argumentos son literales del repo.
    shell: process.platform === "win32",
  },
);

hijo.on("exit", (codigo) => process.exit(codigo ?? 0));
