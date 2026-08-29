import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Armar una promoción sin saberse ningún identificador de memoria.
 *
 * Hasta la 0.8.1 los tres campos de catálogo de este formulario eran cajas de
 * texto que pedían "ids separados por coma": había que ir a otra pantalla,
 * copiar el UUID de cada producto y pegarlo acá. Un id mal copiado no daba
 * error —la promoción se creaba apuntando a un producto inexistente y no se
 * aplicaba nunca—, así que el fallo aparecía en caja y en silencio.
 *
 * La prueba vive en `uso/` y no en `e2e/` porque lo que verifica es que la
 * pantalla se pueda usar (ADR-047), no un flujo del dinero. Y va de punta a
 * punta a propósito: que los productos elegidos lleguen a la base se
 * comprueba leyendo la fila que la tabla dibuja después de crear, que es el
 * único lugar donde se ve lo que se guardó.
 *
 * De paso cubre el riesgo del desplegable dentro de un `<dialog>` nativo: el
 * navegador sube el diálogo al top layer y apaga los eventos de todo lo que
 * quede fuera, así que un popup mal anclado se ve pero no se puede clicar.
 * El `click()` sobre una opción falla si eso pasa — Playwright exige que el
 * elemento reciba el evento de verdad.
 */

const PRECIO_DEL_COMBO = "25";

test("una promoción se arma buscando los productos, sin teclear ids", async ({
  page,
}, testInfo) => {
  await ingresar(page, ADMIN);

  await page.goto("/ventas/promociones");
  await expect(page.getByRole("heading", { name: /Promociones/i })).toBeVisible();
  await capturar(page, testInfo, "promociones-listado");

  await page.getByRole("button", { name: "+ Nueva promoción" }).click();
  await dialogo(page).getByLabel("Nombre").fill("Combo E2E");
  await dialogo(page).getByRole("radio", { name: /Combo/ }).check();
  await dialogo(page)
    .getByLabel("Precio fijo del combo (S/)")
    .fill(PRECIO_DEL_COMBO);

  // Lo que antes era "ids separados por coma": se escribe parte del nombre y
  // se elige de lo que queda.
  // Por rol y nombre, no por placeholder: en un combo hay dos buscadores de
  // producto —los del combo y el que va gratis— y comparten el marcador.
  const buscador = dialogo(page).getByRole("combobox", {
    name: "Productos del combo",
  });
  await buscador.click();
  await buscador.fill("Pizza");

  const primera = dialogo(page).getByRole("option").first();
  await expect(primera).toBeVisible();
  await capturar(page, testInfo, "desplegable-filtrado");
  await primera.click();

  // El segundo producto del combo: el buscador queda listo para el siguiente
  // sin cerrar el diálogo ni perder lo ya elegido.
  await buscador.fill("Mitad");
  await dialogo(page).getByRole("option").first().click();

  // Cada elección queda como una etiqueta con su ✕, que es lo que permite
  // revisar lo elegido sin volver a abrir la lista.
  const quitar = dialogo(page).getByRole("button", { name: /^Quitar / });
  await expect(quitar).toHaveCount(2);
  await capturar(page, testInfo, "dos-productos-elegidos");

  await dialogo(page).getByRole("button", { name: "Crear" }).click();

  // La fila lo confirma desde la base: `comoSeLeeCombo` cuenta los
  // `producto_ids` que el servidor guardó, así que este texto solo aparece si
  // los dos identificadores viajaron completos.
  await expect(page.getByRole("row", { name: /Combo E2E/ })).toBeVisible();
  await expect(
    page.getByText(`2 productos a S/ ${PRECIO_DEL_COMBO}`),
  ).toBeVisible();
  await capturar(page, testInfo, "promocion-creada");

  // Reabrir el diálogo empieza de cero. `DialogoFormulario` deja los hijos
  // montados y llama `form.reset()`, que vacía los `<input>` del navegador
  // pero no toca el estado de React: sin escuchar ese reset, la segunda
  // promoción del día nacía con los productos de la primera ya puestos.
  await page.getByRole("button", { name: "+ Nueva promoción" }).click();
  await dialogo(page).getByRole("radio", { name: /Combo/ }).check();
  await expect(
    dialogo(page).getByRole("button", { name: /^Quitar / }),
  ).toHaveCount(0);
});
