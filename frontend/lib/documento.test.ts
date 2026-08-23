import assert from "node:assert/strict";
import { test } from "node:test";

import { documentoValido, tipoPorLargo } from "./documento.ts";

/**
 * El largo decide a quién se le pregunta (RN-CPP-003). Importa porque es lo
 * que hace que un solo campo —el de caja, donde el cliente dicta su número
 * sin decir qué es— sepa si va a RENIEC o a SUNAT sin preguntarle al cajero.
 */

test("ocho dígitos es DNI, once es RUC", () => {
  assert.equal(tipoPorLargo("44556677"), "dni");
  assert.equal(tipoPorLargo("20610077782"), "ruc");
});

test("un largo intermedio no se adivina", () => {
  // Tecleando, un RUC pasa por 8 dígitos: por eso el botón consulta cuando
  // se lo aprieta y no solo, en cada tecla.
  assert.equal(tipoPorLargo("4455667"), null);
  assert.equal(tipoPorLargo("206100777"), null);
  assert.equal(tipoPorLargo(""), null);
});

test("lo que no son dígitos no es documento", () => {
  assert.equal(tipoPorLargo("4455667a"), null);
  assert.equal(tipoPorLargo("       "), null);
});

test("los espacios de los costados no cuentan", () => {
  assert.equal(tipoPorLargo("  44556677  "), "dni");
});

test("sin documento la venta sigue siendo válida", () => {
  assert.equal(documentoValido(""), true);
  assert.equal(documentoValido("44556677"), true);
  assert.equal(documentoValido("445566"), false);
});
