import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * El recorrido que motivó ADR-051: el local arma su requerimiento de la
 * jornada, le suma algo que el stock no pidió, lo envía y lo aprueban; y
 * después cuenta su almacén.
 *
 * El escenario lo pone `src/seeders/e2e.py`: el almacén del local tiene dos
 * insumos bajo su mínimo y uno sobrado. Sin ese punto de reorden la lista
 * saldría vacía y la prueba pasaría por vacía.
 */

const ALMACEN_LOCAL = "Almacén Tarapoto Centro";

test("el local arma su requerimiento y el almacén ve qué es urgencia", async ({
  page,
}, testInfo) => {
  await page.goto("/login");
  await ingresar(page, ADMIN);

  await page.goto("/inventario/solicitudes");
  await expect(
    page.getByRole("heading", { name: /Requerimientos/i }),
  ).toBeVisible();
  await capturar(page, testInfo, "requerimientos-listado");

  await page
    .getByLabel("Almacén del requerimiento")
    .selectOption({ label: ALMACEN_LOCAL });
  await page.getByRole("button", { name: "Requerimiento de la jornada" }).click();

  // La lista llega armada: los dos insumos bajo mínimo ya están adentro.
  await expect(page.getByRole("heading", { name: /Requerimiento de la jornada/i })).toBeVisible();
  await expect(page.getByText("Bajo mínimo", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/2 bajo mínimo/)).toBeVisible();
  await capturar(page, testInfo, "borrador-con-lo-bajo-minimo");

  // Y lo que el local decide pedir aparte queda marcado como no urgente.
  await page.getByRole("button", { name: "+ Agregar producto" }).click();
  await dialogo(page).getByLabel("Producto").selectOption({ index: 1 });
  await dialogo(page).getByRole("button", { name: "Agregar" }).click();
  await expect(page.getByText("Pedido del local", { exact: true })).toBeVisible();
  await expect(page.getByText(/1 a pedido del local/)).toBeVisible();
  await capturar(page, testInfo, "borrador-con-pedido-del-local");

  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("pendiente")).toBeVisible();
  // Ya enviado deja de editarse: no hay cómo agregar ni quitar.
  await expect(page.getByRole("button", { name: "+ Agregar producto" })).toHaveCount(0);
  await capturar(page, testInfo, "requerimiento-enviado");
});

test("el almacén cuenta su stock y el cierre pide los ajustes", async ({
  page,
}, testInfo) => {
  await page.goto("/login");
  await ingresar(page, ADMIN);

  await page.goto("/inventario/conteos");
  await expect(page.getByRole("heading", { name: /^Conteos/i })).toBeVisible();
  await capturar(page, testInfo, "conteos-listado");

  await page.getByRole("button", { name: "+ Abrir conteo" }).click();
  // Por `name` y no por etiqueta: el nombre accesible de un `<select>` suma
  // el texto de sus opciones, y «Todo el almacén» del selector de al lado
  // también contiene "almacén".
  await dialogo(page)
    .locator('select[name="almacen_id"]')
    .selectOption({ label: ALMACEN_LOCAL });
  await dialogo(page).getByRole("button", { name: "Abrir" }).click();

  await expect(page.getByRole("heading", { name: /Toma de inventario/i })).toBeVisible();
  await capturar(page, testInfo, "toma-de-inventario");

  // El recorrido lo hace `admin`, que **sí** tiene `ver_stock_esperado`: por
  // eso la columna «Sistema» está. A ciegas (RN-INV-005) es lo que ve quien
  // solo tiene `inventory.contar`, y eso lo fija `tests/test_conteos.py`
  // —acá haría falta sembrar un almacenero solo para mirar una columna que
  // no está—.
  await expect(page.getByRole("columnheader", { name: "Sistema" })).toBeVisible();

  const contados = page.getByRole("textbox", { name: /^Contado de / });
  await contados.first().fill("1");
  await page.getByRole("button", { name: "Guardar lo contado" }).click();
  await expect(page.getByText(/Guardado: 1 producto/)).toBeVisible();

  await page.getByRole("button", { name: "Cerrar conteo" }).click();
  await expect(page.getByText(/Conteo cerrado/)).toBeVisible();
  await capturar(page, testInfo, "conteo-cerrado");
});
