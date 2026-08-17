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
/** **Recibe** el efectivo al final del turno: el tramo
 * `en_caja → en_supervisor` lo firma quien recibe (RN-MDP-002) y para eso
 * hace falta alguien distinto del cajero. Abrir y cerrar ya no lo necesitan
 * (RN-MDP-008, ADR-049). */
export const ENCARGADO = { usuario: "encargado_e2e", pin: "654321" };
/** El rol con menos permisos que igual opera una pantalla: con él se
 * verifica qué **no** se ve, y desde ADR-049 también que puede abrir y
 * cerrar su turno sin ayuda de nadie. */
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
  //
  // Se ancla al saludo y no al subtítulo: «Hola, <usuario>» es el dato que la
  // pantalla tiene que mostrar —de hecho confirma de quién es la sesión, que
  // es lo que estas suites verifican—, mientras que la bajada de abajo es
  // copy y cambia cada vez que alguien la mejora. Pasó exactamente eso: el
  // rediseño la cambió por «Elige por dónde empezar» y siete pruebas se
  // cayeron sin que nada estuviera roto.
  await expect(
    page.getByRole("heading", { name: new RegExp(`Hola, ${quien.usuario}`, "i") }),
  ).toBeVisible({ timeout: 30_000 });
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

/** Teclea un PIN en el pinpad (ADR-045). No hay `<input>` que llenar: el
 * PIN se toca dígito por dígito, que es justamente lo que impide que el
 * navegador ofrezca guardarlo.
 *
 * Se busca por testid a nivel de página y no dentro de `dialogo()` porque
 * el bloqueo de pantalla es OTRO `<dialog open>` por encima: acotar a
 * `dialog[open]` encontraría dos y Playwright lo rechaza. Cada pinpad tiene
 * su testid propio, así que a nivel de página igual hay uno solo. */
export async function tecleaPin(page: Page, testid: string, pin: string) {
  const teclas = page.getByTestId(testid);
  for (const digito of pin) {
    await teclas.getByRole("button", { name: digito, exact: true }).click();
  }
}
