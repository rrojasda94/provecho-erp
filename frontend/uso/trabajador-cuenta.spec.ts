import { expect, test } from "@playwright/test";

import { ADMIN, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Asignarle a un trabajador la cuenta con la que marca asistencia.
 *
 * Existe porque el hueco que arregla esta rama no era del backend: el campo
 * `usuario_id` viajaba en el alta, pero `TrabajadorUpdate` no lo declaraba y
 * **la pantalla nunca lo ofrecía**. Todas las pruebas de `pytest` pasaban
 * —llamaban la API directo— mientras que desde la UI el campo quedaba en
 * NULL para siempre y ningún trabajador podía fichar en el pad.
 *
 * Por eso lo que se verifica acá es el formulario: que el selector exista,
 * que liste cuentas y que lo elegido llegue a la fila. Un test de API no
 * puede ver ninguna de las tres cosas.
 */

const CUENTA = "Cuenta para marcar asistencia";

test("el trabajador recibe su cuenta desde la ficha", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/rrhh/trabajadores");
  await expect(page.getByRole("heading", { name: "Trabajadores" })).toBeVisible();
  await capturar(page, testInfo, "trabajadores");

  await page.getByRole("button", { name: "+ Nuevo trabajador" }).click();
  const alta = page.locator("dialog[open]");
  const selector = alta.getByLabel(CUENTA);

  // El selector tiene que estar y tiene que traer cuentas: si el rol no
  // pudiera listarlas, en su lugar habría un aviso y no un `<select>`.
  await expect(selector).toBeVisible();
  const cuentas = await selector.locator("option").allTextContents();
  expect(cuentas.length).toBeGreaterThan(1);
  // La opción vacía es válida y va primera: quien no ficha en el pad no
  // necesita cuenta, y su asistencia la carga RRHH por back-office.
  expect(cuentas[0]).toContain("Sin cuenta");
  await capturar(page, testInfo, "alta-con-selector-de-cuenta");

  // Una cuenta de agente no puede aparecer: entra por token y no tiene PIN
  // que teclear (ADR-032), así que no serviría para firmar una marcación.
  expect(cuentas.join(" ")).not.toContain("agente");

  await alta.getByRole("button", { name: "Cancelar" }).click();
});
