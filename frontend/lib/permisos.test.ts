import assert from "node:assert/strict";
import { test } from "node:test";

import { CONSULTA_DOCUMENTO, puedeConsultarDocumento } from "./permisos.ts";

/**
 * El gate del botón «Buscar por DNI/RUC» (ADR-041).
 *
 * Se prueba la función y no el componente porque `npm test` corre sobre Node
 * pelado: type-stripping sí, transformación de JSX no. Por eso la regla vive
 * en `lib/permisos.ts` y `BuscarDocumento` no hace más que preguntarle —lo
 * que quedaría sin cubrir es una línea (`if (!puede…) return null`), y que
 * ninguna pantalla pueda montar el botón sin decir de quién es la sesión lo
 * garantiza `tsc`: `permisos` es una prop obligatoria.
 *
 * Que esto importe no es teórico: sin el gate, un `contador` o un
 * `almacenero` veía el botón y se comía un 403 dibujado como aviso. Y cada
 * consulta que sí sale gasta cuota de un proveedor pago, así que esconder
 * es mejor que mostrar y fallar.
 */

test("sin el permiso no se ofrece la consulta", () => {
  assert.equal(puedeConsultarDocumento([]), false);
  // Un contador tiene lo suyo y nada de esto: ver el padrón de clientes no
  // trae de arrastre poder barrer RUCs.
  assert.equal(puedeConsultarDocumento(["accounting.leer", "sales.leer"]), false);
});

test("con el permiso se ofrece", () => {
  assert.equal(puedeConsultarDocumento([CONSULTA_DOCUMENTO]), true);
  assert.equal(puedeConsultarDocumento(["sales.crear", CONSULTA_DOCUMENTO]), true);
});

test("el comodín del admin también", () => {
  assert.equal(puedeConsultarDocumento(["*"]), true);
});

test("un permiso que solo empieza igual no alcanza", () => {
  // `tieneAccesoModulo` mira prefijos; este gate no. Un permiso futuro
  // `consulta.documento_masivo` no puede habilitar el botón de al lado.
  assert.equal(puedeConsultarDocumento(["consulta.documento_masivo"]), false);
});
