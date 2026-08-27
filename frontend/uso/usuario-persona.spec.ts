import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Vincular una persona a una cuenta desde Usuarios, y que ese vínculo se vea
 * al reabrir el editor y habilite al pad de asistencia (ADR-070).
 *
 * Reemplaza a `trabajador-cuenta.spec.ts`: el vínculo cuenta↔trabajador
 * vivía duplicado en dos columnas que nadie sincronizaba —
 * `usuario.persona_id` (esta pantalla) y `trabajador.usuario_id` (un
 * selector en RRHH → Trabajadores, ya retirado) — y vincular desde acá no
 * hacía nada para el pad. Todas las pruebas de `pytest` pasaban porque
 * llamaban la API directo; lo que hacía falta ver desde la UI era que (a) el
 * campo, tal como se guarda, se pinta de vuelta al reabrir el diálogo —
 * antes se veía siempre vacío aunque el vínculo sí se hubiera guardado — y
 * (b) que ese mismo guardado, sin tocar RRHH, deja al trabajador marcar.
 *
 * Sembrada por `src/seeders/e2e.py` (`_sembrar_rrhh`): una persona sin
 * cuenta todavía — si ya viniera vinculada, la prueba no podría distinguir
 * "se guardó" de "ya estaba".
 */

const CUENTA = "cajero1";
const PERSONA_BUSQUEDA = "Vinculable E2E";
const PERSONA_ETIQUETA = "Vinculable E2E, Elena — 88880001";

test("vincular la persona desde Usuarios se ve al reabrir y habilita el pad", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);
  await page.goto("/usuarios");
  await expect(page.getByRole("heading", { name: "Cuentas" })).toBeVisible();
  await capturar(page, testInfo, "usuarios");

  await page
    .getByRole("row")
    .filter({ hasText: CUENTA })
    .getByRole("button", { name: "Editar" })
    .click();
  const editor = dialogo(page);
  await expect(editor.getByRole("heading", { name: `Editar ${CUENTA}` })).toBeVisible();

  const buscador = editor.getByPlaceholder("Buscar por nombre o documento...");
  await buscador.fill(PERSONA_BUSQUEDA);
  await editor.getByRole("button", { name: PERSONA_ETIQUETA }).click();
  await capturar(page, testInfo, "persona-elegida");

  await editor.getByRole("button", { name: "Guardar" }).click();
  await expect(editor).toBeHidden();

  // El bug reportado: reabrir el editor y ver la persona que se guardó, no
  // un campo vacío.
  await page
    .getByRole("row")
    .filter({ hasText: CUENTA })
    .getByRole("button", { name: "Editar" })
    .click();
  const reabierto = dialogo(page);
  await expect(reabierto.getByPlaceholder("Buscar por nombre o documento...")).toHaveValue(
    PERSONA_ETIQUETA,
  );
  await capturar(page, testInfo, "persona-visible-al-reabrir");
  await reabierto.getByRole("button", { name: "Cancelar" }).click();

  // Y el efecto real: sin tocar RRHH → Trabajadores, el trabajador de esa
  // persona ya puede marcar en el pad.
  await page.goto("/rrhh/trabajadores");
  await expect(page.getByRole("heading", { name: "Trabajadores" })).toBeVisible();
  const fila = page.getByRole("row").filter({ hasText: "Vinculable E2E" });
  await expect(fila).toContainText("sí");
  await capturar(page, testInfo, "trabajador-marca-si");
});
