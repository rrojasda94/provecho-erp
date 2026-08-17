import { expect, test, type Page } from "@playwright/test";

import { ADMIN, CAJERO, ENCARGADO, contar, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * El turno de un cajero, de punta a punta y con la cadena de custodia
 * completa (ADR-049).
 *
 * Es el recorrido que **no puede vivir en `e2e/`**: cruza dos identidades y
 * dos módulos —el PDV del cajero y la pantalla de caja de contabilidad—, y
 * el techo de la suite de e2e son tres casos que bloquean cada merge. Acá lo
 * que se entrega son las capturas: la secuencia de pantallas que muestra que
 * un cajero puede trabajar su turno **sin que nadie venga a poner su PIN**, y
 * que el efectivo igual queda a nombre de alguien en cada tramo.
 *
 * Lo que verifica, en orden:
 *
 * 1. El cajero abre su caja solo (RN-MDP-008). Antes de ADR-049 este paso
 *    era imposible con esta sesión: el diálogo pedía el PIN de un encargado
 *    y el rol `cajero` ni siquiera tiene el permiso que esa firma exige.
 * 2. Vende y cobra.
 * 3. Cierra su caja solo, y el efectivo queda **en el cajón, a su nombre**
 *    (`en_caja`) — no entregado a un encargado que no estuvo.
 * 4. El encargado firma la recepción en `/contabilidad/caja` con su usuario
 *    y PIN, y el tramo pasa a `en_supervisor` (RN-MDP-002).
 *
 * La pantalla del paso 4 la abre el `admin`: listar turnos cerrados exige
 * `accounting.leer` y el rol `supervisor` no lo tiene todavía (anotado como
 * deuda en `docs/roadmap/deuda/dashboard-y-caja.md`). No desvirtúa el
 * recorrido —toda elevación por PIN funciona así, quien firma aporta su PIN
 * sobre la pantalla de otro— pero conviene tenerlo presente al mirar las
 * capturas.
 *
 * Datos: `python -m src.seeders.seed` + `python -m src.seeders.e2e`.
 */

const PRODUCTO = "Pizza E2E";

async function salir(page: Page, usuario: string) {
  await page
    .getByRole("button", { name: new RegExp(`Sesión de ${usuario}`, "i") })
    .click();
  await page.getByRole("menuitem", { name: /Cerrar sesión/i }).click();
  await expect(page).toHaveURL(/\/login/);
}

test("el cajero abre, vende y cierra solo; el encargado firma la recepción", async ({
  page,
}, testInfo) => {
  // --- 1. El cajero abre su turno ------------------------------------------
  await ingresar(page, CAJERO);
  await page.goto("/pdv");
  await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();
  await capturar(page, testInfo, "apertura-sin-firma");

  await contar(page, { "100": 1, "50": 2 }); // 200.00
  await dialogo(page).getByTestId("apertura-declarado").fill("200");
  await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
  await expect(page.getByTestId("estado-caja")).toContainText("Caja abierta", {
    timeout: 30_000,
  });
  await capturar(page, testInfo, "caja-abierta");

  // --- 2. Vende y cobra -----------------------------------------------------
  await page.getByRole("button", { name: new RegExp(PRODUCTO, "i") }).first().click();
  await dialogo(page).getByRole("button", { name: /Guardar/i }).click();
  await page.getByRole("button", { name: /^Cobrar$/i }).click();
  // El PDV no deja salir del borrador sin tipo de orden (RN-COM-005): el
  // primer "Cobrar" abre el diálogo de tipo, no el de cobro.
  await expect(dialogo(page).getByText("Tipo de orden")).toBeVisible();
  await dialogo(page).getByRole("button", { name: /Para llevar/i }).click();
  await dialogo(page).getByRole("button", { name: /^Confirmar$/ }).click();

  await page.getByRole("button", { name: /^Cobrar$/i }).click();
  await expect(dialogo(page).getByText("Cobrar", { exact: true })).toBeVisible();
  await capturar(page, testInfo, "cobro");
  await dialogo(page).getByRole("button", { name: /^Confirmar pago$/ }).click();
  await expect(page.getByTestId("estado-caja")).toContainText("Caja abierta");

  // --- 3. Cierra su turno, también solo ------------------------------------
  await page.getByTestId("estado-caja").click();
  await expect(dialogo(page).getByText("Cierre de caja")).toBeVisible();
  // 200 de apertura + 25 cobrados en efectivo: se cuenta lo que hay.
  await contar(page, { "100": 2, "20": 1, "5": 1 });
  // **Hallazgo del recorrido**: al cajero no le aparece ningún terminal que
  // cuadrar, porque listar los POS de la sucursal exige `accounting.leer` y
  // su rol no lo tiene — el PDV se come el 403 y muestra la lista vacía. No
  // lo causa ADR-049 (la apertura siempre corrió sobre la sesión del
  // cajero), pero ahora que él es el operador esperado, RN-POS-010 queda
  // muerta en la práctica. Anotado en `docs/roadmap/deuda/dashboard-y-caja.md`.
  // El bucle se escribe igual para que el día que se arregle el permiso este
  // recorrido cubra el cuadre de tarjetas sin tocar una línea.
  for (const lote of await dialogo(page).getByTestId(/^lote-/).all()) {
    await lote.fill("0");
  }
  await dialogo(page).getByTestId("cierre-custodia").selectOption("local_caja_fuerte");
  await capturar(page, testInfo, "cierre-sin-firma");
  await dialogo(page).getByRole("button", { name: "Cerrar caja" }).click();
  await expect(page.getByTestId("estado-caja")).toContainText("Caja cerrada", {
    timeout: 30_000,
  });

  // --- 4. El encargado recibe el efectivo ----------------------------------
  await page.goto("/");
  await salir(page, CAJERO.usuario);
  await ingresar(page, ADMIN);
  await page.goto("/contabilidad/caja");

  const fila = page.locator("tr", { hasText: "Recibe el encargado" }).first();
  await expect(fila).toBeVisible({ timeout: 30_000 });
  // El tramo con el que nace la custodia desde ADR-049: la plata sigue en el
  // cajón y el responsable es el cajero que cerró.
  await expect(fila).toContainText(/en el cajón/i);
  await capturar(page, testInfo, "turno-cerrado-en-el-cajon");

  await fila.getByRole("button", { name: "Recibe el encargado" }).click();
  const firma = page.locator("dialog[open]");
  await expect(firma.getByText("Recibir el efectivo")).toBeVisible();
  await firma.getByLabel("Usuario").fill(ENCARGADO.usuario);
  await firma.getByLabel("PIN").fill(ENCARGADO.pin);
  await capturar(page, testInfo, "firma-del-encargado");
  await firma.getByRole("button", { name: /Firmar/ }).click();

  // El tramo avanzó: el efectivo pasó a estar con el encargado, y el
  // siguiente paso que ofrece la pantalla ya es el de contabilidad.
  await expect(
    page.locator("tr", { hasText: "Recibe contabilidad" }).first(),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/con el encargado/i).first()).toBeVisible();
  await capturar(page, testInfo, "efectivo-con-el-encargado");
});
