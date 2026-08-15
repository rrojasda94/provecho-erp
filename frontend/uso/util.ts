import type { Page, TestInfo } from "@playwright/test";

/**
 * Lo propio de las pruebas de uso. Las credenciales y el `ingresar()` no se
 * duplican acá: viven en `../e2e/util` y son los mismos, porque el seeder es
 * el mismo (`src/seeders/e2e.py`). Un segundo juego de PINs se desincroniza
 * del seeder el día que alguien cambie uno.
 *
 * No es `.spec.ts` a propósito: Playwright solo recolecta
 * `*.spec.ts`/`*.test.ts`, así que este archivo no corre como prueba vacía.
 */

const hitos = new WeakMap<TestInfo, number>();

/**
 * Captura un hito del recorrido.
 *
 * Se numeran solos y en orden de ejecución: el entregable de esta suite es
 * la carpeta de imágenes, y una carpeta ordenada por nombre de archivo se
 * puede leer como una secuencia. Con nombres sueltos, `home.png` aparece
 * antes que `login.png` y el recorrido se lee al revés.
 *
 * `outputPath()` las deja dentro del `outputDir` de la config de uso, que es
 * lo que CI sube como artefacto. Escribir a una ruta propia las dejaría
 * fuera del artefacto y también fuera del `.gitignore` — las capturas
 * **nunca** se versionan.
 *
 * Sin `testInfo.attach()`: adjuntar **copia** el archivo a `attachments/`, y
 * el resultado era cada captura dos veces en el artefacto. Lo único que
 * aportaba era verla desde el visor de trazas, que con `trace: "on"` ya
 * tiene una captura por acción.
 */
export async function capturar(page: Page, info: TestInfo, nombre: string) {
  const numero = (hitos.get(info) ?? 0) + 1;
  hitos.set(info, numero);

  const archivo = info.outputPath(`${String(numero).padStart(2, "0")}-${nombre}.png`);
  await page.screenshot({ path: archivo, fullPage: true });
}
