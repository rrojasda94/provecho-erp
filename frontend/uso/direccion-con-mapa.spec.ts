import { expect, test } from "@playwright/test";

import { ADMIN, dialogo, ingresar } from "../e2e/util";
import { capturar } from "./util";

/**
 * Recorrido: el campo de dirección **con** el mapa encendido.
 *
 * El gemelo de `direccion.spec.ts`, que corre sin clave. Faltaba éste, y esa
 * falta costó caro: el 2026-08-25, encendiendo Google en staging, el mapa no
 * aparecía nunca. No era la clave ni las restricciones —el SDK cargaba,
 * `window.google` existía, `PlaceAutocompleteElement` se construía— sino un
 * bloqueo mutuo en el componente: el contenedor del buscador estaba
 * condicionado a `conMapa`, y el efecto que pone `conMapa` en `true`
 * necesitaba ese contenedor para montar el buscador. Salía antes por su
 * `if (!buscadorRef.current) return`, en silencio. La integración estuvo
 * muerta desde que se escribió y ninguna prueba podía verlo, porque la única
 * que tocaba el campo corría sin clave y ese camino ni se ejecutaba.
 *
 * **El SDK lo responde Playwright, no Google.** Interceptar la carga en vez
 * de pedirla de verdad es lo que hace que esta prueba no gaste cuota de un
 * proveedor pago, no necesite red y no se ponga roja el día que Google ande
 * lento. De paso cubre algo más: la respuesta llega desde
 * `maps.googleapis.com`, así que si alguien saca ese host de la CSP de
 * `middleware.ts`, el navegador la bloquea y esto se cae.
 *
 * Lo que **no** se prueba acá sigue siendo lo mismo que en el gemelo: que el
 * autocompletado de Google mapee bien sus resultados. Eso exige a Google.
 */

/** Sembrada por `src/seeders/seed.py` (`SUCURSALES`). */
const SUCURSAL = "CH2";

/** Nombre del elemento falso: sirve además como selector en las asertivas. */
const BUSCADOR = "gmp-buscador-de-mentira";

/**
 * Lo mínimo del SDK que `campo-direccion.tsx` toca al montar: pedir la
 * librería `places` y construir un `PlaceAutocompleteElement`. Un
 * `HTMLElement` alcanza — el componente le pone `placeholder`, un ancho y un
 * listener, y lo cuelga del DOM.
 */
const SDK_FALSO = `
  class BuscadorFalso extends HTMLElement {}
  customElements.define(${JSON.stringify(BUSCADOR)}, BuscadorFalso);
  window.google = {
    maps: {
      importLibrary: async (nombre) =>
        nombre === "places" ? { PlaceAutocompleteElement: BuscadorFalso } : {},
    },
  };
`;

test("con clave puesta, el buscador de Google aparece en el campo", async ({
  page,
}, testInfo) => {
  await page.route("https://maps.googleapis.com/maps/api/js*", (ruta) =>
    ruta.fulfill({ contentType: "application/javascript", body: SDK_FALSO }),
  );

  await ingresar(page, ADMIN);
  await page.getByRole("link", { name: /^Organización/ }).click();
  await page.locator("aside").getByRole("link", { name: "Sucursales" }).click();
  await expect(page.getByRole("heading", { name: "Sucursales" })).toBeVisible();

  await page
    .getByRole("row")
    .filter({ hasText: SUCURSAL })
    .getByRole("button", { name: "Editar" })
    .click();
  const formulario = dialogo(page);
  await expect(
    formulario.getByRole("heading", { name: "Editar sucursal" }),
  ).toBeVisible();

  // Lo que estaba roto: el buscador tiene que llegar al DOM.
  await expect(formulario.locator(BUSCADOR)).toBeAttached();
  // Y el aviso tiene que dejar de decir que no hay mapa. Es la misma bandera
  // (`conMapa`) leída desde la pantalla, que es donde se nota.
  await expect(formulario.getByRole("status")).toContainText(/Busca la dirección/i);
  await capturar(page, testInfo, "campo-con-mapa");

  // El campo de texto sigue siendo el que manda: con mapa o sin él, lo que
  // viaja en el formulario es este input (ADR-053).
  await expect(formulario.getByLabel("Dirección")).toBeEditable();
});
