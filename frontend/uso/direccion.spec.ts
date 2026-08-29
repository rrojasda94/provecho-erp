import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Recorrido: corregir la dirección de una sucursal con el mapa apagado.
 *
 * **Corre sin clave de Google, y ese es el punto.** El servidor de la suite
 * arranca sin `GOOGLE_MAPS_BROWSER_KEY`, así que el SDK ni se pide y el campo
 * queda como el `<input>` de siempre. Eso es exactamente lo que hay que poder
 * afirmar (ADR-053):
 *
 * - En el hub offline de una sucursal no hay internet, y el ERP se sigue
 *   operando.
 * - En Tarapoto hay calles que Google no conoce.
 * - La clave se puede quedar sin cuota un martes a las ocho de la noche.
 *
 * Si este recorrido se pone rojo, la integración dejó de ser opcional y el
 * ERP quedó dependiendo de que un tercero conteste para guardar una ficha.
 *
 * Que el autocompletado mapee bien cuando Google **sí** contesta no se prueba
 * acá: sería gastar cuota de un proveedor pago en cada rama y volver roja la
 * suite cada vez que Google tenga un mal día. Mismo criterio que
 * `consulta-documento.spec.ts`.
 */

/** Sembrada por `src/seeders/seed.py` (`SUCURSALES`). */
const SUCURSAL = "CH2";
const DIRECCION_NUEVA = "Jr. Alegría Arias de Morey 1234 - Tarapoto";

test("una dirección escrita a mano se guarda igual sin mapa", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);
  await capturar(page, testInfo, "home");

  await page.getByRole("link", { name: /^Organización/ }).click();
  await page.locator("aside").getByRole("link", { name: "Sucursales" }).click();
  await expect(page.getByRole("heading", { name: "Sucursales" })).toBeVisible();
  await capturar(page, testInfo, "sucursales");

  await page
    .getByRole("row")
    .filter({ hasText: SUCURSAL })
    .getByRole("button", { name: "Editar" })
    .click();
  const formulario = dialogo(page);
  await expect(
    formulario.getByRole("heading", { name: "Editar sucursal" }),
  ).toBeVisible();

  // Sin clave no hay lista de sugerencias ni mapa: el campo de texto es todo
  // lo que hay, y tiene que alcanzar.
  const direccion = formulario.getByLabel("Dirección");
  await expect(direccion).toBeVisible();
  await expect(formulario.getByRole("status")).toContainText(/no está disponible/i);
  // El punto de ADR-072: sin SDK el campo es un `<input>` pelado, no un
  // combobox — nada de `role`, nada de lista, aunque el desplegable propio
  // exista en el código.
  await expect(direccion).not.toHaveAttribute("role", "combobox");
  await expect(formulario.getByRole("listbox")).toHaveCount(0);
  // Los cinco ocultos existen y están vacíos: es lo que rompería primero un
  // refactor del render que hoy nadie verifica.
  for (const campo of [
    "ubicacion_place_id",
    "ubicacion_lat",
    "ubicacion_lng",
    "ubicacion_plus_code",
    "ubicacion_distrito",
  ]) {
    await expect(formulario.locator(`input[name="${campo}"]`)).toHaveValue("");
  }
  await capturar(page, testInfo, "campo-sin-mapa");

  await direccion.fill(DIRECCION_NUEVA);
  await formulario.getByRole("button", { name: "Guardar" }).click();

  // Y quedó guardada: un campo que se escribe pero no persiste sería el mismo
  // agujero que tenía la dirección de delivery del PDV hasta este cambio.
  await expect(page.getByRole("cell", { name: DIRECCION_NUEVA })).toBeVisible();
  await capturar(page, testInfo, "direccion-corregida");
});
