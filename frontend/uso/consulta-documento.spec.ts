import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Recorrido: corregir la razón social de un cliente jurídico trayéndola de
 * SUNAT (ADR-041).
 *
 * Existe por un reporte concreto —«la búsqueda por DNI o RUC aún no está
 * visible»—: el botón estaba montado en Personas y en Proveedores, pero no
 * en Ventas → Clientes, que es donde el propio diálogo promete que «SUNAT
 * manda sobre la razón social tecleada». Lo que este recorrido deja probado
 * es que ahora **está**, y que la pantalla se banca que el proveedor no
 * conteste.
 *
 * **No se prueba contra Factiliza de verdad, y es deliberado.**
 * `e2e/servidor-api.mjs` arranca la API con `FACTILIZA_TOKEN: ""`, así que
 * el cliente ni sale a la red y el endpoint responde 502. Hacerlo de otra
 * forma sería peor por tres razones y ninguna es la comodidad:
 *
 * 1. Cada consulta gasta cuota de un proveedor **pago**, y una suite que
 *    corre en cada rama la gastaría sola.
 * 2. La respuesta sería datos personales reales de alguien —de un DNI que
 *    existe— entrando a un artefacto de CI que se sube y se guarda.
 * 3. Un tercero caído volvería roja una suite que no tiene nada roto.
 *
 * Lo que sí se verifica acá es lo que el ERP controla: que el botón se
 * ofrezca, que el fallo del proveedor se explique en la pantalla en vez de
 * romperla, y que el alta **siga siendo posible tecleando** — que es el
 * criterio de ADR-005 y la razón por la que esto prellena y no decide. Que
 * la respuesta se mapee bien cuando el proveedor sí contesta lo cubren los
 * dobles de `tests/test_factiliza_consulta.py`, que es donde se puede
 * afirmar sin gastar un centavo.
 */

/** Sembrado por `src/seeders/e2e.py` (`CLIENTE_RUC`), con la razón social
 * tecleada mal a propósito: sin eso no hay nada que corregir. */
const RUC = "20610077782";
const RAZON_SOCIAL_REAL = "SERVICIOS RENTAURANT S.A.C";

test("el padrón de clientes ofrece traer la razón social del RUC", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);
  await capturar(page, testInfo, "home");

  // Se navega por el shell y no con un `goto` directo: el reporte era que el
  // botón "no está visible", así que llegar como llega quien lo busca es
  // parte de lo que se verifica.
  await page.getByRole("link", { name: /^Ventas/ }).click();
  // Acotado al sidebar del módulo (`ModuloShell`) y no a `getByRole
  // ("navigation")`: el rastro de migas es otro `<nav>` y Playwright rechaza
  // un locator que encuentra dos.
  await page.locator("aside").getByRole("link", { name: "Clientes" }).click();
  await expect(page.getByRole("heading", { name: "Clientes" })).toBeVisible();
  await capturar(page, testInfo, "padron-de-clientes");

  // Por el RUC y no por la razón social: el RUC es lo que el seeder fija y
  // la razón social es justo lo que este recorrido va a cambiar.
  await page
    .getByRole("row")
    .filter({ hasText: RUC })
    .getByRole("button", { name: "Editar" })
    .click();
  const formulario = dialogo(page);
  await expect(formulario.getByRole("heading", { name: "Editar cliente" })).toBeVisible();

  const buscar = formulario.getByRole("button", { name: /Buscar por RUC/ });
  await expect(buscar).toBeVisible();
  await capturar(page, testInfo, "boton-buscar-por-ruc");

  await buscar.click();
  // El aviso, no la excepción: sin token la API responde 502 y la pantalla
  // tiene que decirlo donde se está tecleando. Un `role="status"` vacío o un
  // diálogo que se cierra solo serían las dos formas de fallar mal.
  await expect(formulario.getByRole("status")).not.toBeEmpty();
  await capturar(page, testInfo, "el-proveedor-no-contesta");

  // Y el alta sigue: se teclea a mano, que es el punto de "prellena, no
  // decide" (ADR-005).
  await formulario.getByLabel("Razón social").fill(RAZON_SOCIAL_REAL);
  await formulario.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByRole("cell", { name: RAZON_SOCIAL_REAL })).toBeVisible();
  await capturar(page, testInfo, "corregido-a-mano");
});
