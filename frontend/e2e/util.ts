import { expect, type Page } from "@playwright/test";

/**
 * Lo que comparten las suites e2e. No es `.spec.ts` a propósito: Playwright
 * solo recolecta `*.spec.ts`/`*.test.ts`, así que este archivo no corre como
 * prueba vacía.
 *
 * Los PIN son los del seeder `src/seeders/e2e.py`, que es la fuente — si
 * cambian allá, cambian acá.
 */

export const ADMIN = { usuario: "admin", pin: "123456" };
/** Releva la caja: abrir exige que quien firma **no** sea el cajero
 * (RN-MDP-002), así que la suite necesita dos personas. */
export const ENCARGADO = { usuario: "encargado_e2e", pin: "654321" };
/** El rol con menos permisos que igual opera una pantalla: con él se
 * verifica qué **no** se ve. */
export const CAJERO = { usuario: "cajero_e2e", pin: "111111" };

export async function ingresar(page: Page, quien = ADMIN) {
  await page.goto("/login");
  await page.getByRole("textbox").first().fill(quien.usuario);
  await page.locator('input[type="password"]').fill(quien.pin);
  await page.getByRole("button", { name: "Ingresar" }).click();
  // Se espera el **contenido** del destino, no la navegación: el `redirect`
  // de una Server Action lo resuelve el cliente sin recargar, así que nunca
  // se dispara el evento `load` que `waitForURL` espera por defecto y la
  // prueba se queda mirando una página que ya cambió.
  await expect(page.getByText(/Elige un módulo/i)).toBeVisible({ timeout: 30_000 });
}

/** El diálogo visible. Los de apertura y cierre están **los dos montados**
 * en el DOM —solo uno abierto— y comparten los testids del conteo por
 * denominación, así que buscar por testid a nivel de página encuentra dos
 * elementos y Playwright lo rechaza. Acotar al `dialog[open]` es también lo
 * correcto: la prueba interactúa con lo que el cajero ve. */
export function dialogo(page: Page) {
  return page.locator("dialog[open]");
}

/** Teclea el conteo por denominación. Las claves son el valor del billete,
 * igual que el `detalle_denominaciones` que viaja al servidor. */
export async function contar(page: Page, conteo: Record<string, number>) {
  for (const [valor, piezas] of Object.entries(conteo)) {
    await dialogo(page).getByTestId(`denom-${valor}`).fill(String(piezas));
  }
}
