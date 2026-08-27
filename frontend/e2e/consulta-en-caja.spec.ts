import { expect, test } from "@playwright/test";

import { contar, dialogo, ingresar } from "./util";

/**
 * El botón «Buscar DNI / RUC» en el **alta de cliente** del PDV — el otro
 * punto de caja donde nace alguien que todavía no está registrado (el del
 * comprobante se recorre dentro de `caja.spec.ts`, que ya llega al diálogo
 * de cobro con la venta armada).
 *
 * Lo que se verifica acá es lo que el ERP controla, no lo que responde
 * Factiliza: que el botón esté, que el largo decida a qué padrón se le
 * pregunta **antes** de salir a la red, y que el alta siga siendo posible
 * tecleando cuando el proveedor no contesta.
 *
 * **No se prueba contra Factiliza de verdad, y es deliberado** — mismo
 * criterio que `uso/consulta-documento.spec.ts`: `e2e/servidor-api.mjs`
 * arranca la API sin token, así que el cliente ni sale a la red. Cada
 * consulta gasta cuota de un proveedor **pago**, la respuesta serían datos
 * personales reales de alguien entrando a un artefacto de CI, y un tercero
 * caído volvería roja una suite que no tiene nada roto. Que el mapeo esté
 * bien cuando el proveedor sí contesta lo cubren los dobles de
 * `tests/test_factiliza_consulta.py`.
 */

test("en caja, el largo del documento decide el padrón antes de gastar cuota", async ({
  page,
}) => {
  await ingresar(page);
  await page.goto("/pdv");

  // La apertura de caja es bloqueante y tapa todo lo demás. Este recorrido
  // no es sobre el dinero, así que se la saca de encima con lo mínimo — y
  // **solo si hace falta**: la base de la suite es compartida y el turno
  // puede venir abierto de otro archivo. Dar por hecho que está cerrada
  // hacía fallar la prueba con "no aparece la apertura", que no dice nada
  // del botón que se está probando.
  const estado = page.getByTestId("estado-caja");
  await expect(estado).toBeVisible({ timeout: 15_000 });
  if (!(await estado.textContent())?.includes("Caja abierta")) {
    await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();
    await contar(page, { "100": 1 });
    await dialogo(page).getByTestId("apertura-declarado").fill("100");
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
    await expect(estado).toContainText("Caja abierta", { timeout: 15_000 });
  }

  await page.getByRole("button", { name: "Cliente", exact: true }).click();
  await dialogo(page).getByRole("button", { name: /Crear cliente nuevo/ }).click();

  const buscar = dialogo(page).getByRole("button", { name: "Buscar DNI / RUC" });
  await expect(buscar).toBeVisible();

  const documento = dialogo(page).getByLabel("DNI o RUC del cliente");

  // Un largo que no es ni DNI ni RUC **no se consulta**: tecleando, un RUC
  // pasa por 8 dígitos, así que salir a la red con lo que haya escrito
  // gastaría una cuota para prellenar con los datos de otra persona.
  await documento.fill("206100777");
  await buscar.click();
  await expect(dialogo(page).getByTestId("aviso-consulta-documento")).toContainText(/8 dígitos/);

  // Con un largo válido sí sale, y sin proveedor el aviso lo dice donde se
  // está tecleando en vez de romper la pantalla.
  await documento.fill("72471723");
  await buscar.click();
  await expect(dialogo(page).getByTestId("aviso-consulta-documento")).not.toBeEmpty();
  await expect(dialogo(page).getByTestId("aviso-consulta-documento")).not.toContainText(/8 dígitos/);

  // Y el alta sigue tecleando, que es el punto de "prellena, no decide"
  // (ADR-005): el cliente se guarda igual.
  await dialogo(page).getByLabel("Nombre del cliente").fill("Cliente Tecleado E2E");
  await dialogo(page).getByLabel("Teléfono del cliente").fill("942111222");
  await dialogo(page).getByRole("button", { name: "Guardar cliente" }).click();
  await expect(dialogo(page)).toBeHidden();
});
