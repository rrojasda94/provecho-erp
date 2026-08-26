import { expect, test } from "@playwright/test";

import { ADMIN, contar, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * El configurador de una pizza mitad-y-mitad.
 *
 * Es el recorrido que faltaba: la carta no traía los atributos, así que el
 * diálogo mostraba únicamente la lista de «Sin…» —larguísima— y ninguna
 * opción de sabor. Peor, «Guardar» quedaba habilitado, la línea se cobraba
 * sin sabores y la receta condicionada no descontaba **ningún** insumo.
 * Toda la suite de backend estaba en verde mientras eso pasaba, porque el
 * hueco vivía entre la carta y la pantalla.
 *
 * Se prueba acá y no con `node --test` porque lo que se rompió es el
 * ensamblado: `lib/opciones-pdv.test.ts` cubre las reglas puras.
 */

const PRODUCTO = "Mitad y Mitad E2E";

test("la pizza mitad y mitad pide un sabor por mitad", async ({ page }, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/pdv");

  // Sin caja abierta el PDV no muestra la carta: el candado es parte del
  // diseño (ADR-025), así que el recorrido pasa por la apertura. Pero puede
  // venir abierta de otro recorrido de la misma suite —la caja es del punto
  // de venta y vive en el servidor, no en el navegador— así que no se asume
  // cerrada: se abre solo si hace falta (mismo patrón que
  // `delivery-gerencia.spec.ts`).
  const caja = page.getByTestId("estado-caja");
  await expect(caja).toBeVisible({ timeout: 30_000 });
  if ((await caja.textContent())?.includes("cerrada")) {
    await contar(page, { "100": 1, "50": 2 });
    await dialogo(page).getByTestId("apertura-declarado").fill("200");
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
  }
  await expect(caja).toContainText("Caja abierta", { timeout: 30_000 });

  // Sin `exact`: el botón del catálogo lleva el precio dentro, así que su
  // nombre accesible es «Mitad y Mitad E2E S/ 30.00». Mismo criterio que
  // `e2e/caja.spec.ts`.
  await page.getByRole("button", { name: new RegExp(PRODUCTO, "i") }).first().click();
  await expect(dialogo(page)).toBeVisible();
  await capturar(page, testInfo, "configurador");

  // Los dos atributos salen, cada uno con sus sabores.
  await expect(dialogo(page).getByText("Mitad 1 E2E · obligatorio")).toBeVisible();
  await expect(dialogo(page).getByText("Mitad 2 E2E · obligatorio")).toBeVisible();

  // El «Sin…» arranca colapsado: con una receta larga tapaba justamente
  // esto. El encabezado se ve; las pastillas, no.
  const plegable = dialogo(page).locator("details.pdv-plegable");
  await expect(plegable).toHaveCount(1);
  await expect(plegable).not.toHaveAttribute("open", /.*/);

  // Sin elegir sabores no se puede guardar, y el pie dice cuál falta.
  await expect(dialogo(page).getByText("Elige Mitad 1 E2E")).toBeVisible();
  await expect(dialogo(page).getByRole("button", { name: "Guardar" })).toBeDisabled();

  // Elegido «Queso E2E» en la primera mitad, el mismo sabor queda apagado en
  // la segunda: media y media del mismo sabor es una pizza entera.
  const bloque = (nombre: string) =>
    dialogo(page).getByTestId("pdv-atributo").filter({ hasText: nombre });
  const mitad1 = bloque("Mitad 1 E2E");
  const mitad2 = bloque("Mitad 2 E2E");
  await mitad1.getByRole("button", { name: "Queso E2E" }).click();
  await expect(mitad2.getByRole("button", { name: "Queso E2E" })).toBeDisabled();
  await capturar(page, testInfo, "sabor-repetido-apagado");

  // Con la otra mitad distinta, la línea ya se puede guardar.
  await mitad2.getByRole("button", { name: "Papa E2E" }).click();
  await expect(dialogo(page).getByRole("button", { name: "Guardar" })).toBeEnabled();
  await dialogo(page).getByRole("button", { name: "Guardar" }).click();

  // Y el ticket dice qué mitades son: sin esto, dos mitad-y-mitad distintas
  // se ven idénticas en la comanda y en la pantalla.
  await expect(page.getByText("Mitad 1 E2E: Queso E2E")).toBeVisible();
  await expect(page.getByText("Mitad 2 E2E: Papa E2E")).toBeVisible();
  await capturar(page, testInfo, "ticket-con-sabores");
});
