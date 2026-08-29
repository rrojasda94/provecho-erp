import { expect, type Locator, type Page } from "@playwright/test";

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
/** Cuenta de sacrificio de la prueba del lockout: la prueba la deja
 * bloqueada 15 minutos, así que no puede ser ninguna de las tres de arriba
 * —el orden entre archivos no está prometido y la siguiente que la usara se
 * quedaría afuera—. */
export const BLOQUEABLE = { usuario: "bloqueo_e2e", pin: "222222" };
/** Nadie. Un usuario inexistente devuelve el mismo 401 que un PIN
 * equivocado (anti-enumeración, `auth.login`) **sin gastarle un intento del
 * lockout a ninguna cuenta de verdad**: es la forma barata de mirar cómo se
 * ve el rechazo. */
export const FANTASMA = { usuario: "no_existe_e2e", pin: "999999" };

/** El pinpad del login (ADR-050). Los del PDV tienen el suyo. */
export const PINPAD_LOGIN = "login-pin";
/** Los dígitos que pide un PIN (`rules.PIN_LENGTH`). */
export const LARGO_PIN = 6;

/** El único campo de texto del login. Se exporta porque hay pruebas que
 * afirman **lo que quedó escrito en él** después de un rechazo. */
export function campoUsuario(page: Page) {
  return page.getByRole("textbox").first();
}

/** El aviso de error del login, con su `data-motivo`.
 *
 * Por testid y no por `getByRole("alert")`: Next monta su propio
 * `<div role="alert">` para anunciar cambios de ruta, así que buscar por rol
 * encuentra dos y Playwright lo rechaza. */
export function avisoLogin(page: Page) {
  return page.getByTestId("login-error");
}

/**
 * Teclea el PIN en el pinpad del login, esperando a que la página hidrate.
 *
 * El primer toque puede caer **antes de que React tome la pantalla**: el
 * botón ya está en el DOM porque vino del servidor, y el clic no hace nada.
 * El síntoma es un PIN al que le falta un dígito —que por eso nunca llega a
 * seis y ni siquiera se envía—, sin ningún error a la vista: la corrida
 * muere después, esperando un home que nadie pidió. Con `next dev`
 * compilando la ruta en frío la ventana dura segundos, y antes de ADR-050 no
 * existía porque el formulario se enviaba solo (Server Action en `action`,
 * que funciona sin JavaScript) — con el PIN tocado eso ya no es posible.
 *
 * El reintento **borra primero**: sin eso el segundo intento apila dígitos
 * sobre los que sí entraron y manda un PIN equivocado, gastando uno de los
 * cinco del lockout.
 */
export async function tecleaPinLogin(page: Page, pin: string) {
  const pinpad = page.getByTestId(PINPAD_LOGIN);
  const tecla = (d: string) => pinpad.getByRole("button", { name: d, exact: true });

  await expect(async () => {
    await pinpad.getByRole("button", { name: "Borrar todo" }).click();
    await tecla(pin[0]).click();
    await expect(avancePinpad(page)).toHaveText(`1 de ${LARGO_PIN} dígitos`, {
      timeout: 2_000,
    });
  }).toPass({ timeout: 60_000 });

  for (const digito of pin.slice(1)) await tecla(digito).click();
}

export async function ingresar(page: Page, quien = ADMIN) {
  await page.goto("/login");
  await campoUsuario(page).fill(quien.usuario);
  // El PIN se toca, no se escribe: desde ADR-050 el login tampoco tiene
  // `<input type="password">` que llenar. Y no se hace clic en "Ingresar" —
  // el sexto dígito ya envía (`onCompleto`), así que el clic mandaría el
  // formulario por segunda vez.
  await tecleaPinLogin(page, quien.pin);
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
/**
 * Elige una opción de un desplegable con búsqueda (`components/ui/combobox`).
 *
 * Reemplaza al `selectOption()` de los `<select>` que estos campos eran hasta
 * la 0.8.2: ahora hay que teclear y hacer clic en la opción. Vive acá y no en
 * cada prueba porque son tres pasos que se repiten y que, escritos a mano,
 * cada spec ancla distinto.
 *
 * `exact` en los dos localizadores a propósito: los nombres de campo se
 * solapan —«Almacén» es prefijo de «Almacén del requerimiento»— y sin él la
 * misma búsqueda encuentra dos.
 */
export async function elegirEnLista(
  ambito: Page | Locator,
  campo: string,
  opcion: string,
) {
  const buscador = ambito.getByRole("combobox", { name: campo, exact: true });
  // El clic va antes que el texto: sin foco explícito el desplegable no abre
  // el popup, y `fill()` deja el valor puesto pero ninguna opción para
  // clicar — la búsqueda queda esperando algo que nunca aparece.
  await buscador.click();
  await buscador.fill(opcion);
  await ambito.getByRole("option", { name: opcion, exact: true }).click();
}

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

/** La región viva del pinpad: "N de 6 dígitos". Es la única señal de que un
 * toque registró —los puntos son `aria-hidden`— y por eso una prueba la
 * afirma. Sirve además de sincronización entre intentos: tras un rechazo el
 * PIN se vacía y esto vuelve a "0 de 6", que es cuando el pinpad vuelve a
 * aceptar dígitos. */
export function avancePinpad(page: Page, largo = LARGO_PIN) {
  return page.getByText(new RegExp(`^\\d+ de ${largo} dígitos$`));
}
